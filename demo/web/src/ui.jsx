import React from 'react';

const shapes = {
  voice: <><path d="M3 10v4m4-7v10m5-13v16m5-13v10m4-7v4"/></>,
  mic: <><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/></>,
  play: <path d="m8 5 12 7-12 7z"/>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2"/>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
  send: <><path d="m21 3-7 18-4-7-7-4 18-7zM10 14l11-11"/></>,
  stack: <><path d="m3 8 9-5 9 5-9 5-9-5zM3 12l9 5 9-5m-18 4 9 5 9-5"/></>,
  branch: <><circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10m0-4h5a7 7 0 0 0 7-5"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></>,
  terminal: <><path d="m5 6 6 6-6 6m8 0h6"/></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2 7m2-12v5h-5"/></>,
  chart: <><path d="M4 3v17h17M8 16v-4m5 4V8m5 8V5"/></>,
  volume: <><path d="M3 10v4h4l5 4V6l-5 4H3zm13-2a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/></>,
  shield: <><path d="M12 22s7-4 7-10V5l-7-3-7 3v7c0 6 7 10 7 10z"/><path d="m9 12 2 2 4-4"/></>,
};
export function Icon({ name, size = 18 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}
export const modeLabels = { bare: 'Bare', prompt_only: 'Prompt only', harness: 'Harness' };
const readable = value => String(value ?? '').replaceAll('_', ' ');
const caps = value => readable(value).replace(/^./, x => x.toUpperCase());

export function SectionTitle({ icon, title, children }) {
  return <div className="section-title"><h2><Icon name={icon} /> {title}</h2>{children}</div>;
}

export function ScriptCards({ scenarios, selected, select, disabled }) {
  return <section className="panel scenario-panel">
    <SectionTitle icon="stack" title="Scenario" />
    <p className="subtle">Pick a script to show a known failure or try your own staging request.</p>
    <div className="scenario-options">
      {scenarios.map(item => <button key={item.id} type="button" aria-pressed={selected === item.id}
        disabled={disabled} onClick={() => select(item.id)}>
        <span className="scenario-id">{item.id}</span><span>{item.title}</span>
      </button>)}
      <button type="button" aria-pressed={selected === ''} disabled={disabled} onClick={() => select('')}>
        <span className="scenario-id">Free</span><span>Free speech or text</span>
      </button>
    </div>
    {selected && <div className="reference">
      <span className="micro">SCRIPT TO SAY</span>
      <blockquote>“{scenarios.find(item => item.id === selected)?.reference}”</blockquote>
    </div>}
  </section>;
}

export function TranscriptPanel({ dialogue, reference, interim, inputSource, listening, hasSession }) {
  return <section className="panel transcript-panel">
    <SectionTitle icon="voice" title="Transcript">
      {inputSource && <span className="badge">{inputSource === 'typed' ? 'Typed input' : 'Microphone'}</span>}
    </SectionTitle>
    <div className="transcript-feed" aria-live="polite" aria-relevant="additions text">
      {!dialogue.length && !interim && <div className="empty-transcript">
        <span className="empty-icon"><Icon name="voice" size={23}/></span>
        <strong>{hasSession ? (listening ? 'Listening for a request' : 'Ready for a request') : 'Start a staging session'}</strong>
        <p>The request, what the harness heard, and its read-back appear here.</p>
      </div>}
      {dialogue.map(line => line.type === 'caller' ?
        <div className="turn caller" key={line.key}>
          <div className="turn-label">You {line.source && <span className="badge">{line.source}</span>}</div>
          <div>{line.text}</div>
          {line.heard && line.heard !== line.text && <div className="heard"><strong>Heard:</strong> {line.heard}</div>}
          {line.normalized && line.normalized !== (line.heard || line.text) &&
            <div className="heard"><strong>Interpreted:</strong> {line.normalized}</div>}
        </div> : <div className="turn assistant" key={line.key}>
          <div className="turn-label">Assistant {line.cut && <span className="badge warn">Interrupted</span>}</div>
          <div>{line.text || (line.cut ? 'Stopped before a complete word.' : '')}</div>
        </div>)}
      {interim && <div className="turn interim"><div className="turn-label">Hearing now</div>{interim}</div>}
    </div>
    {reference && <div className="script-note"><span className="micro">REFERENCE</span> {reference}</div>}
  </section>;
}

export function BackendPanel({ release, targets, commits }) {
  return <section className="panel backend-panel">
    <SectionTitle icon="terminal" title="Mock deployment"><span className="badge green"><i/> Staging</span></SectionTitle>
    <code className="service-label">checkout-api</code>
    <div className="release"><span>Active release</span><strong>v{release ?? '12'}</strong></div>
    <div className="backend-facts"><div><span>Rollback targets</span><code>{(targets || ['10','11']).map(x => 'v' + x).join(' · ')}</code></div>
      <div><span>Commits this session</span><strong className={commits ? 'accent' : ''}>{commits}</strong></div></div>
  </section>;
}

export function LedgerPanel({ jobs, lastGate }) {
  return <section className="panel ledger-panel">
    <SectionTitle icon="branch" title="Action ledger"/>
    {lastGate?.kind === 'readback' && <p className="gate-note"><Icon name="shield" size={16}/> Waiting for confirmation on release {lastGate.shown_args?.release}.</p>}
    {!jobs.length ? <div className="ledger-empty">No proposed actions yet.</div> :
      <ol>{jobs.map((job, i) => {
        const status = job.to || job.state || 'proposed';
        const className = status.startsWith('done') ? 'green' : status === 'cancelled' ? 'warn' : '';
        return <li key={job.job ?? job.id ?? i}>
          <div><span>{caps(job.name)}</span>{job.out && <small>{caps(job.out)}</small>}</div>
          <span className={'badge ' + className}>{caps(status)}</span>
        </li>;
      })}</ol>}
  </section>;
}

export function Scoreboard({ summary }) {
  return <section className="panel board-panel">
    <SectionTitle icon="chart" title="Scripted benchmark"/>
    <p className="subtle">Offline Plan A runs on synthetic scenarios. Live microphone attempts are separate.</p>
    {summary?.modes ? <div className="table-wrap"><table>
      <thead><tr><th>Mode</th><th>Runs</th><th>Successful</th><th>Wrong target</th><th>Unconfirmed</th></tr></thead>
      <tbody>{summary.modes.map(row => <tr key={row.mode}><th>{modeLabels[row.mode] || row.mode}</th>
        <td>{row.runs}</td><td>{row.successful}</td><td>{row.wrong_commits}</td><td>{row.unconfirmed}</td></tr>)}</tbody>
    </table></div> : <p className="ledger-empty">Benchmark results unavailable.</p>}
  </section>;
}

export function ReplayPlayer({ traces, onPlay, onStop, playing, name, setName, speed, setSpeed }) {
  return <section className="panel replay-panel">
    <SectionTitle icon="play" title="Replay a saved trace"/>
    <p className="subtle">Watch the transcript, deployment and ledger update on the trace’s simulated clock.</p>
    <div className="replay-controls">
      <label>Saved trace<select value={name} onChange={e => setName(e.target.value)} disabled={playing}>
        <option value="">Select a trace</option>
        {traces.map(item => <option key={item.name} value={item.name}>{item.scenario} · {modeLabels[item.mode] || item.mode} · {item.name}</option>)}
      </select></label>
      <label>Speed<select value={speed} onChange={e => setSpeed(Number(e.target.value))} disabled={playing}>
        <option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option>
      </select></label>
      {playing ? <button type="button" className="button secondary" onClick={onStop}><Icon name="stop"/> Stop replay</button> :
        <button type="button" className="button primary" disabled={!name} onClick={onPlay}><Icon name="play"/> Play trace</button>}
    </div>
  </section>;
}

export function MicPanel({ supported, listening, audio, setAudio, micClick, stopSpeech, readback, acknowledge,
  input, setInput, onSubmit, busy, details, speaking }) {
  return <section className="panel mic-panel">
    <SectionTitle icon="mic" title="Session input">
      <label className="audio-control"><input type="checkbox" checked={audio} onChange={e => setAudio(e.target.checked)}/>
        <Icon name="volume" size={17}/> Speak replies</label>
    </SectionTitle>
    <div className="mic-actions">
      <button type="button" className={'button ' + (listening ? 'secondary listening' : 'secondary')}
        onClick={micClick} disabled={!supported || busy} aria-pressed={listening}>
        <Icon name={listening ? 'stop' : 'mic'}/> {listening ? 'Stop mic' : 'Start mic'}
      </button>
      {speaking && <button type="button" className="button secondary" onClick={stopSpeech}><Icon name="stop"/> Stop reply</button>}
      {!supported && <span className="subtle">Microphone recognition unavailable. Type below.</span>}
      {listening && <span className="mic-live" role="status"><i/> Listening</span>}
    </div>
    {readback && <div className="ack-row"><span>Read the reply before continuing. Acknowledging it does not confirm a rollback.</span>
      <button type="button" className="button secondary" disabled={busy} onClick={acknowledge}>I’ve read the reply</button></div>}
    <form className="prompt-form" onSubmit={onSubmit}>
      <label className="sr-only" htmlFor="command">Type a staging request</label>
      <input id="command" value={input} onChange={e => setInput(e.target.value)} maxLength={400}
        placeholder="Type a staging request…" autoComplete="off" />
      <button className="button primary" type="submit" disabled={!input.trim() || busy}><Icon name="send" size={17}/> Send</button>
    </form>
    {details && <p className="subtle details">{details}</p>}
  </section>;
}
