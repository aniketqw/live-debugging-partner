import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BackendPanel, Icon, LedgerPanel, MicPanel, ReplayPlayer, Scoreboard, ScriptCards,
  SectionTitle, TranscriptPanel, modeLabels } from './ui.jsx';
import { createSpeaker, recognitionAvailable, startRecognition } from './speech.js';
import { projectTrace, scheduleReplay } from './replay.js';
import { createScoringArm, validSpeakerCode } from './score.js';
import './styles.css';

const LANG = 'en-IN';
const tabs = [
  ['live', 'Live session', 'voice'],
  ['compare', 'Compare modes', 'branch'],
  ['replay', 'Replay', 'play'],
  ['results', 'Benchmark', 'chart'],
];

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const result = await fetch('/api/' + path, options);
  let data;
  try { data = await result.json(); } catch { data = {}; }
  if (!result.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Request failed (' + result.status + ').');
  return data;
}
const query = (path, key, value) => path + '?' + new URLSearchParams({ [key]: value });

function browserFamily() {
  const ua = navigator.userAgent;
  if (ua.includes('Edg/')) return 'Edge';
  if (ua.includes('Chrome/') || ua.includes('CriOS/')) return 'Chrome';
  if (ua.includes('Firefox/') || ua.includes('FxiOS/')) return 'Firefox';
  if (ua.includes('Safari/')) return 'Safari';
  return 'Other';
}

function App() {
  const [view, setView] = useState('live');
  const [model, setModel] = useState('oracle');
  const [mode, setMode] = useState('harness');
  const [fault, setFault] = useState(0);
  const [scenario, setScenario] = useState('');
  const [models, setModels] = useState([{ name: 'oracle', kind: 'scripted', available: true }]);
  const [scenarios, setScenarios] = useState([]);
  const [traces, setTraces] = useState([]);
  const [summary, setSummary] = useState(null);
  const [connected, setConnected] = useState(false);
  const [session, setSession] = useState(null);
  const [liveTrace, setLiveTrace] = useState([]);
  const [remoteState, setRemoteState] = useState(null);
  const [input, setInput] = useState('');
  const [inputSource, setInputSource] = useState('');
  const [interim, setInterim] = useState('');
  const [listening, setListening] = useState(false);
  const [audio, setAudio] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [readback, setReadback] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [notice, setNotice] = useState('');
  const [scoreArmed, setScoreArmed] = useState(false);
  const [label, setLabel] = useState('');
  const [score, setScore] = useState(null);
  const [compare, setCompare] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [replayName, setReplayName] = useState('');
  const [replayTrace, setReplayTrace] = useState([]);
  const [speed, setSpeed] = useState(2);
  const [playing, setPlaying] = useState(false);
  const player = useRef(null);
  const replayEpoch = useRef(0);
  const visibleView = useRef(view);
  visibleView.current = view;

  const generation = useRef(0);
  const currentSession = useRef(null);
  const evSource = useRef(null);
  const recognition = useRef(null);
  const speaker = useRef(null);
  if (!speaker.current) speaker.current = createSpeaker();
  const pending = useRef(null);
  const audioOn = useRef(audio);
  const serial = useRef(Promise.resolve());
  const timestamp = useRef(0);
  const sessionStarted = useRef(0);
  const scoreArm = useRef(null);
  if (!scoreArm.current) scoreArm.current = createScoringArm();
  const cutBarrier = useRef(Promise.resolve(true));
  const busyOperation = useRef(false);

  useEffect(() => {
    let active = true;
    Promise.allSettled(['models', 'scenarios', 'traces', 'summary'].map(path => api(path))).then(results => {
      if (!active) return;
      const [modelResult, scripts, replays, bench] = results.map(item => item.status === 'fulfilled' ? item.value : null);
      if (modelResult?.models?.length) setModels(modelResult.models);
      if (scripts?.scenarios) {
        setScenarios(scripts.scenarios);
        setScenario(scripts.scenarios.some(card => card.id === 'S2') ? 'S2' : scripts.scenarios[0]?.id || '');
      }
      if (replays?.traces) {
        setTraces(replays.traces);
        setReplayName(replays.traces.find(trace => trace.scenario === 'S2' && trace.mode === 'harness')?.name || replays.traces[0]?.name || '');
      }
      if (bench) setSummary(bench);
      if (!modelResult) setProblem('The staging server is not reachable. Start the local demo server, then reload.');
    });
    return () => {
      active = false;
      currentSession.current = null;
      generation.current++;
      evSource.current?.close();
      recognition.current?.stop();
      speaker.current.cancel();
      player.current?.();
    };
  }, []);

  function enqueue(fn) {
    const result = serial.current.then(fn);
    serial.current = result.catch(() => {});
    return result;
  }

  function acknowledge(reply, payload) {
    if (!reply || pending.current?.speech_id !== reply.speech_id || currentSession.current?.id !== reply.id) {
      return Promise.resolve(true);
    }
    pending.current = null;
    setSpeaking(false);
    setReadback(false);
    return enqueue(async () => {
      if (currentSession.current?.id !== reply.id) return false;
      await api('spoken', { session_id: reply.id, speech_id: reply.speech_id, ...payload });
      return true;
    }).catch(async error => {
      if (currentSession.current?.id !== reply.id) return false;
      setProblem('Could not acknowledge the reply: ' + error.message);
      try {
        const state = await api(query('state', 'session_id', reply.id));
        if (state.active_speech?.speech_id === reply.speech_id && !pending.current &&
            currentSession.current?.id === reply.id) {
          pending.current = { ...reply, audible: false };
          setReadback(true);
        }
      } catch { /* The error stays visible if the server cannot be reached. */ }
      return false;
    });
  }

  function handleSpeak(item, active) {
    if (active.id !== currentSession.current?.id) return;
    const reply = { ...item, id: active.id, audible: false };
    pending.current = reply;
    if (!audioOn.current || visibleView.current !== 'live') {
      setReadback(true);
      return;
    }
    // Only the current speech id can acknowledge the server's active phrase.
    reply.audible = true;
    setReadback(false);
    setSpeaking(true);
    const success = speaker.current.speak(item.text, {
      lang: LANG,
      onEnd: () => acknowledge(reply, { complete: true }),
      onError: () => {
        if (pending.current !== reply) return;
        reply.audible = false;
        setSpeaking(false);
        setReadback(true);
        setNotice('Browser speech output stopped. Read the visible reply to continue.');
      },
    });
    if (!success) {
      reply.audible = false;
      setSpeaking(false);
      setReadback(true);
    }
  }

  function cutCurrent(force = false) {
    const reply = pending.current;
    if (!reply?.audible || (!force && currentSession.current?.mode !== 'harness')) return cutBarrier.current;
    const cut = acknowledge(reply, speaker.current.cancel());
    cutBarrier.current = cut;
    return cut;
  }

  function closeCurrent() {
    currentSession.current = null;
    evSource.current?.close();
    setConnected(false);
    recognition.current?.stop();
    recognition.current = null;
    speaker.current.cancel();
    setListening(false);
    pending.current = null;
    cutBarrier.current = Promise.resolve(true);
    scoreArm.current.clear();
    setScoreArmed(false);
    setReadback(false);
    setSpeaking(false);
    setInterim('');
    setSession(null);
  }

  async function createSession() {
    const state = { mode, model, scenario: scenario || null, fault_p: Number(fault) };
    const run = ++generation.current;
    closeCurrent();
    setLiveTrace([]);
    setRemoteState(null);
    setInputSource('');
    setScore(null);
    setNotice('');
    const response = await api('session', state);
    if (generation.current !== run) return null;
    const active = { ...state, id: response.session_id };
    currentSession.current = active;
    setSession(active);
    sessionStarted.current = performance.now();
    timestamp.current = 0;
    const stream = new EventSource('/api/' + query('events', 'session_id', active.id));
    evSource.current = stream;
    stream.onopen = () => { if (currentSession.current === active) setConnected(true); };
    stream.onerror = () => { if (currentSession.current === active) setConnected(false); };
    const seen = new Set();
    const spoken = new Set();
    stream.addEventListener('trace', event => {
      if (currentSession.current !== active) return;
      const data = JSON.parse(event.data);
      if (seen.has(data.seq)) return;
      seen.add(data.seq);
      timestamp.current = Math.max(timestamp.current, data.t || 0);
      if (data.stage === 'tts' && data.kind === 'cut' && pending.current?.speech_id < data.seq) {
        speaker.current.cancel();
        pending.current = null;
        setSpeaking(false);
        setReadback(false);
      }
      setLiveTrace(trace => [...trace, data]);
    });
    stream.addEventListener('speak', event => {
      if (currentSession.current !== active) return;
      const data = JSON.parse(event.data);
      if (spoken.has(data.speech_id)) return;
      spoken.add(data.speech_id);
      handleSpeak(data, active);
    });
    return active;
  }

  async function newSession() {
    if (busyOperation.current) return;
    busyOperation.current = true;
    setBusy(true);
    setProblem('');
    try { await createSession(); } catch (error) { setProblem(error.message); }
    finally { busyOperation.current = false; setBusy(false); }
  }

  async function postTurn(text, source) {
    setProblem('');
    const trimmed = text.trim();
    if (!trimmed) return;
    const active = currentSession.current || await createSession();
    if (!active) return;
    const attempt = scoreArm.current.take(active.id, source, trimmed);
    if (attempt) setScoreArmed(false);
    // Wait for any in-flight cut, including when recognition only dispatched a final result.
    if (!await cutCurrent()) throw new Error('The speech interruption was not saved. Acknowledge the visible reply or start a new session.');
    return enqueue(async () => {
      if (currentSession.current !== active) return;
      const t_ms = Math.max(timestamp.current, Math.floor(performance.now() - sessionStarted.current));
      await api('utterance', { session_id: active.id, text: trimmed, source, t_ms });
      if (currentSession.current !== active) return;
      setInputSource(source);
      setInterim('');
      if (attempt) {
        try {
          const result = await api('score', { ...attempt, browser: browserFamily(), lang: LANG });
          if (currentSession.current === active) setScore(result);
        } catch (error) {
          if (currentSession.current === active) setNotice('The utterance was sent, but scoring was unavailable: ' + error.message);
        }
      }
      try {
        const state = await api(query('state', 'session_id', active.id));
        if (currentSession.current === active) setRemoteState(state);
      } catch { /* Trace playback does not depend on the snapshot. */ }
    });
  }

  async function submit(event) {
    event.preventDefault();
    if (busyOperation.current || !input.trim()) return;
    const text = input;
    setInput('');
    setBusy(true);
    busyOperation.current = true;
    try { await postTurn(text, 'typed'); }
    catch (error) { setProblem(error.message); setInput(before => before || text); }
    finally { busyOperation.current = false; setBusy(false); }
  }

  function micClick() {
    if (recognition.current?.active) {
      recognition.current.stop();
      return;
    }
    if (!currentSession.current) {
      setNotice('Start a session before enabling the microphone.');
      return;
    }
    setNotice('');
    setProblem('');
    setListening(true);
    recognition.current = startRecognition(LANG, transcript => {
      setInterim(transcript);
      if (transcript) void cutCurrent();
    }, text => {
      postTurn(text, 'speech').catch(error => setProblem(error.message));
    }, () => {
      setListening(false);
      setInterim('');
    }, { onError: reason => {
      setProblem('Microphone recognition stopped (' + reason + '). You can type a request below.');
    } });
    if (!recognition.current?.active) setListening(false);
  }

  function switchView(next) {
    if (next !== 'live') {
      recognition.current?.stop();
      void cutCurrent(true);
    }
    if (next !== 'replay') stopReplay();
    visibleView.current = next;
    setView(next);
  }

  function changeSetting(setter, value) {
    if (busyOperation.current) return;
    if (currentSession.current) {
      closeCurrent();
      setLiveTrace([]);
      setRemoteState(null);
      setInputSource('');
      setScore(null);
      setNotice('Settings changed. Start a new session or send a typed request.');
    }
    setter(value);
  }

  function changeAudio(value) {
    audioOn.current = value;
    setAudio(value);
    if (!value) void cutCurrent(true);
    if (value && !speaker.current.supported) setNotice('This browser cannot speak replies. Visible replies can still be acknowledged.');
  }

  function stopReplay() {
    replayEpoch.current++;
    player.current?.();
    player.current = null;
    setPlaying(false);
  }

  async function playReplay() {
    if (playing || !replayName) return;
    setProblem('');
    setPlaying(true);
    setReplayTrace([]);
    const token = ++replayEpoch.current;
    try {
      const { trace } = await api(query('trace', 'name', replayName));
      if (token !== replayEpoch.current) return;
      player.current = scheduleReplay(trace, event => setReplayTrace(previous => [...previous, event]), stopReplay, { speed });
    } catch (error) {
      if (token !== replayEpoch.current) return;
      setPlaying(false);
      setProblem(error.message);
    }
  }

  function changeScoreArm() {
    if (scoreArmed) {
      scoreArm.current.clear();
      setScoreArmed(false);
      return;
    }
    const active = currentSession.current;
    scoreArm.current.arm({ sessionId: active.id, scenario: active.scenario, speaker_label: label });
    setScore(null);
    setScoreArmed(true);
  }

  async function runCompare() {
    if (comparing) return;
    setProblem('');
    setComparing(true);
    try { setCompare(await api('compare')); }
    catch (error) { setProblem(error.message); }
    finally { setComparing(false); }
  }

  const live = useMemo(() => projectTrace(liveTrace), [liveTrace]);
  const replay = useMemo(() => projectTrace(replayTrace), [replayTrace]);
  const activeScenario = scenarios.find(item => item.id === scenario);
  const release = remoteState?.backend?.services?.['checkout-api'];
  const listeningSupported = recognitionAvailable();

  return <div className="application">
    <a className="skip" href="#workspace">Skip to workspace</a>
    <header className="topbar">
      <div className="top-inner">
        <div className="brand"><span className="brand-icon"><Icon name="voice" size={23}/></span>
          <div><strong>Voice Harness</strong><span>Staging lab</span></div></div>
        <div className="top-chips"><span className="badge green"><i/> Local sandbox</span>
          <span className="badge top-sim">Simulation</span></div>
      </div>
    </header>

    <main id="workspace" className="shell">
      <div className="page-heading">
        <div><p className="eyebrow"><span/> STAGING SIMULATION</p>
          <h1>Rollback console</h1>
          <p>Try a release command. See what was heard, what was confirmed, and what changed.</p></div>
        {view === 'live' && <button type="button" className="button primary hero-button" onClick={newSession} disabled={busy}>
          <Icon name={session ? 'refresh' : 'play'}/> {session ? 'New session' : 'Start session'}</button>}
      </div>
      <nav className="tabs" aria-label="Workspace">
        {tabs.map(([id, text, icon]) => <button type="button" key={id} aria-current={view === id ? 'page' : undefined}
          onClick={() => switchView(id)}><Icon name={icon} size={17}/>{text}</button>)}
      </nav>

      {problem && <div className="message error" role="alert"><Icon name="info"/>{problem}</div>}
      {notice && <div className="message" role="status"><Icon name="info"/>{notice}</div>}

      {view === 'live' && <>
        <section className="control-strip" aria-label="Session settings">
          <label>Execution mode<select value={mode} onChange={e => changeSetting(setMode, e.target.value)} disabled={busy}>
            {Object.entries(modeLabels).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select></label>
          <label>Model<select value={model} onChange={e => changeSetting(setModel, e.target.value)} disabled={busy}>
            {models.map(item => <option key={item.name} value={item.name} disabled={item.available === false}>
              {item.name.replaceAll('_', ' ')}{item.available === false ? ' (unavailable)' : ''}
            </option>)}
          </select></label>
          <label className="range-label"><span>Simulated fault rate <output>{Math.round(fault * 100)}%</output></span>
            <input type="range" min="0" max="0.30" step="0.01" value={fault} onChange={e => changeSetting(setFault, Number(e.target.value))} disabled={busy}/></label>
          <div className="status-col"><span className="micro">CONNECTION</span>
            <span className={'badge ' + (connected ? 'green' : '')}><i/> {connected ? 'Live' : session ? 'Connecting' : 'Idle'}</span></div>
        </section>
        <div className="workspace-grid">
          <div className="workspace-main">
            <TranscriptPanel dialogue={live.dialogue} reference={activeScenario?.reference}
              interim={interim} inputSource={inputSource} listening={listening} hasSession={!!session} />
            <MicPanel supported={listeningSupported} listening={listening} audio={audio} setAudio={changeAudio}
              micClick={micClick} stopSpeech={() => void cutCurrent(true)} speaking={speaking}
              readback={readback} acknowledge={() => {
                cutBarrier.current = acknowledge(pending.current, { complete: true });
              }}
              input={input} setInput={setInput} onSubmit={submit} busy={busy}
              details="Use synthetic staging phrases only. Your browser or its speech provider may process microphone audio." />
          </div>
          <div className="workspace-side">
            <BackendPanel release={live.commits ? live.release : release?.active_release || live.release}
              commits={live.commits} targets={release?.rollback_targets}/>
            <LedgerPanel jobs={live.jobs} lastGate={live.lastGate}/>
            <ScriptCards scenarios={scenarios} selected={scenario}
              select={value => changeSetting(setScenario, value)} disabled={busy}/>
            <section className="panel score-panel">
              <SectionTitle icon="chart" title="Recognition sample"/>
              <p className="subtle">Optional. Record one synthetic microphone transcript locally and compare its digits with the selected script. Typed requests are excluded.</p>
              <label>Speaker code (no real name)<input placeholder="e.g. A or B2" value={label} maxLength={3}
                pattern="[A-Za-z][0-9]{0,2}" disabled={scoreArmed} onChange={e => setLabel(e.target.value)}/></label>
              <button type="button" className="button secondary score-arm"
                disabled={!scoreArmed && (!session?.scenario || !validSpeakerCode(label) || !listeningSupported)}
                onClick={changeScoreArm}>{scoreArmed ? 'Cancel recording' : 'Score my next spoken attempt'}</button>
              {scoreArmed && <p className="subtle" role="status">Read the shown script as your next microphone utterance. Only that utterance will be recorded.</p>}
              {score?.recorded && <p className={'score-outcome ' + (score.digit_exact ? 'match' : '')}>
                {score.digit_exact ? 'Digits match' : 'Digits differ'} · expected {displayDigits(score.expected_digits)} · heard {displayDigits(score.heard_digits)}
              </p>}
            </section>
          </div>
        </div>
      </>}

      {view === 'compare' && <>
        <section className="panel compare-intro">
          <div><SectionTitle icon="branch" title="Same request. Different outcome."/>
            <p className="subtle">Run the same simulated mishearing with the confirmation gate off and on.</p></div>
          <button type="button" className="button primary" onClick={runCompare} disabled={comparing}>
            <Icon name="play"/> {comparing ? 'Running…' : 'Run comparison'}</button>
        </section>
        {compare && <div className="compare-results">
          <div className="example-dialogue"><div><span className="micro">CALLER INTENDED</span><p>{compare.reference}</p></div>
            <div><span className="micro">SIMULATED TRANSCRIPT</span><p>{compare.heard}</p></div></div>
          <div className="side-by-side">
            {[['bare', 'Harness off'], ['harness', 'Harness on']].map(([key, title]) => {
              const result = compare[key];
              const projection = projectTrace(result.trace, result.initial_release);
              return <section className={'panel compare-card ' + key} key={key}>
                <SectionTitle icon={key === 'harness' ? 'shield' : 'terminal'} title={title}/>
                <div className="compare-release"><span>v{result.initial_release}</span>
                  <Icon name="arrow" size={24}/><strong>v{result.final_release}</strong></div>
                <span className="micro">MOCK BACKEND CHANGE</span>
                <ol className="compare-turns">
                  {projection.dialogue.filter(line => line.type === 'assistant').map(line =>
                    <li key={line.key}>{line.text || 'Speech interrupted.'}</li>)}
                </ol>
              </section>;
            })}
          </div>
          <p className="subtle compare-caption">This is a single scripted example, not a benchmark result.</p>
        </div>}
      </>}

      {view === 'replay' && <>
        <ReplayPlayer traces={traces} onPlay={playReplay} onStop={stopReplay} playing={playing}
          name={replayName} setName={setReplayName} speed={speed} setSpeed={setSpeed}/>
        <div className="workspace-grid replay-grid">
          <TranscriptPanel dialogue={replay.dialogue} hasSession={false}/>
          <div className="workspace-side"><BackendPanel release={replay.release} commits={replay.commits}/>
            <LedgerPanel jobs={replay.jobs} lastGate={replay.lastGate}/></div>
        </div>
      </>}

      {view === 'results' && <Scoreboard summary={summary}/>}
      <footer><Icon name="info" size={17}/>
        <span>Browser demo only. No phone calls, real deployments, or recogniser benchmark.</span></footer>
    </main>
  </div>;
}

function displayDigits(value) {
  return Array.isArray(value) ? value.join(' ') || 'none' : value || 'none';
}

createRoot(document.getElementById('root')).render(<App/>);
