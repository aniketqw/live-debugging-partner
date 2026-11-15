import assert from 'node:assert/strict';
import test from 'node:test';
import { createScoringArm, validSpeakerCode } from './score.js';

test('speaker code matches the server format', () => {
  for (const code of ['A', 'A02', 'a9']) assert.equal(validSpeakerCode(code), true, code);
  for (const code of ['12', 'name', 'A_1', 'A123', 'A1 ']) assert.equal(validSpeakerCode(code), false, code);
});

test('only the next microphone utterance of the armed session is accepted', () => {
  const scorer = createScoringArm();
  scorer.arm({ sessionId: 'one', scenario: 'S2', speaker_label: 'A1' });
  assert.equal(scorer.take('one', 'typed', 'typed attempt'), null);
  assert.equal(scorer.take('two', 'speech', 'another session'), null);
  assert.deepEqual(scorer.take('one', 'speech', 'one one'), {
    scenario: 'S2', speaker_label: 'A1', transcript: 'one one', source: 'speech', consent: true,
  });
  assert.equal(scorer.take('one', 'speech', 'yes'), null);
  scorer.arm({ sessionId: 'one', scenario: 'S2', speaker_label: 'B' });
  scorer.clear();
  assert.equal(scorer.take('one', 'speech', 'one one'), null);
});
