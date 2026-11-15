export function scheduleReplay(trace, display, onEnd, { speed = 1, set = setTimeout, clear = clearTimeout } = {}) {
  if (!Number.isFinite(speed) || speed <= 0) throw new RangeError('speed must be positive');
  const base = trace[0]?.t || 0;
  const offset = entry => Math.max(0, (entry.t - base) / speed);
  const handles = trace.map(event => set(() => display(event), offset(event)));
  handles.push(set(onEnd, trace.length ? offset(trace.at(-1)) : 0));
  return () => handles.forEach(clear);
}

export function projectTrace(trace, initialRelease = '12') {
  const jobs = new Map(), turns = new Map();
  let release = initialRelease, lastGate = null, commits = 0;
  const dialogue = [];
  for (const event of trace) {
    const { stage, kind, data = {} } = event;
    if (stage === 'caller' && kind === 'say') {
      const turn = { key: event.seq, type: 'caller', text: data.text, heard: '', normalized: '', source: data.source };
      dialogue.push(turn);
      turns.set(data.turn, turn);
    }
    if (stage === 'asr' && kind === 'out' && turns.has(data.turn)) {
      const turn = turns.get(data.turn);
      turn.heard = data.transcript;
      turn.source = data.source ?? turn.source;
    }
    if (stage === 'norm' && kind === 'out' && turns.has(data.turn)) turns.get(data.turn).normalized = data.text;
    if (stage === 'tts' && kind === 'start') dialogue.push({ key: event.seq, type: 'assistant', text: data.text });
    if (stage === 'tts' && kind === 'cut') {
      const spoken = dialogue.findLast(line => line.type === 'assistant');
      if (spoken) { spoken.cut = true; spoken.text = data.spoken_prefix; }
    }
    if (stage === 'ledger' && kind === 'transition') jobs.set(data.job, { ...jobs.get(data.job), ...data });
    if (stage === 'gate') lastGate = { kind, ...data };
    if (stage === 'tool' && kind === 'exec' && data.ok && data.name === 'rollback_deployment') {
      release = data.result?.active_release || data.args?.release || release;
      commits++;
    }
    if (stage === 'call' && kind === 'end') release = data.final_state?.services?.['checkout-api']?.active_release || release;
  }
  return { release, jobs: [...jobs.values()].reverse(), lastGate, dialogue, commits };
}
