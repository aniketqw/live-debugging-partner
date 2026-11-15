import assert from 'node:assert/strict';
import { test } from 'node:test';
import { scheduleReplay, projectTrace } from './replay.js';

test('replay preserves order and scales simulated timestamps', () => {
  const jobs = [];
  const trace = [{ seq: 0, t: 10 }, { seq: 1, t: 10 }, { seq: 2, t: 30 }];
  const displayed = [];
  const stopped = [];
  const cancel = scheduleReplay(trace, x => displayed.push(x.seq), () => displayed.push('end'), {
    speed: 2, set: (fn, ms) => (jobs.push({ fn, ms }) - 1), clear: id => stopped.push(id),
  });
  assert.deepEqual(jobs.map(x => x.ms), [0, 0, 10, 10]);
  jobs.forEach(x => x.fn());
  assert.deepEqual(displayed, [0, 1, 2, 'end']);
  cancel();
  assert.deepEqual(stopped, [0, 1, 2, 3]);
});

test('trace projection advances ledger and only applies successful rollback events', () => {
  const job = (to) => ({stage:'ledger', kind:'transition', data:{job:1, name:'rollback_deployment', to}});
  const attempt = (ok) => ({
    stage:'tool', kind:'exec', data:{name:'rollback_deployment', ok, args:{release:'11'}, result:{active_release:'11'}},
  });
  assert.equal(projectTrace([job('announced'), attempt(false)]).release, '12');
  const state = projectTrace([job('announced'), attempt(false), attempt(true), job('done_irreversible')]);
  assert.equal(state.release, '11');
  assert.equal(state.jobs[0].to, 'done_irreversible');
});
