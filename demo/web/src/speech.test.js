import assert from 'node:assert/strict';
import { test } from 'node:test';
import { completedWords, createSpeaker, startRecognition } from './speech.js';

test('completed prefix is conservative before start and inside the next word', () => {
  const text = 'Roll  back to one one.';
  assert.deepEqual(completedWords(text, 0), { spoken_prefix: '', n_words: 0 });
  assert.deepEqual(completedWords(text, 8), { spoken_prefix: 'Roll', n_words: 1 });
  assert.deepEqual(completedWords(text, 11), { spoken_prefix: 'Roll back', n_words: 2 });
  assert.deepEqual(completedWords(text, text.length), { spoken_prefix: 'Roll back to one one.', n_words: 5 });
});

test('speaker uses boundary indices and invalidates callbacks after cancellation', () => {
  class Utterance { constructor(text) { this.text = text; } }
  let said;
  const api = { SpeechSynthesisUtterance: Utterance, speechSynthesis: {
    speak(value) { said = value; }, cancel() { said.onend?.(); },
  } };
  let ends = 0;
  const speaker = createSpeaker(api);
  assert.equal(speaker.speak('one two three', { onEnd: () => ends++ }), true);
  said.onboundary({ name: 'word', charIndex: 4 });
  said.onboundary({ name: 'sentence', charIndex: 12 });
  assert.deepEqual(speaker.cancel(), { spoken_prefix: 'one', n_words: 1 });
  assert.equal(ends, 0);
  speaker.speak('one', { onEnd: () => ends++ });
  said.onend();
  assert.equal(ends, 1);
  assert.deepEqual(speaker.cancel(), { spoken_prefix: '', n_words: 0 });
});

test('mic final segments only send once and silence restarts until stopped', () => {
  let object;
  const callbacks = [];
  class Recognition {
    constructor() { object = this; this.starts = 0; }
    start() { this.starts++; }
    abort() { this.onend(); }
  }
  const outputs = [];
  const recognition = startRecognition('en-IN', x => outputs.push(['interim', x]), x => outputs.push(['final', x]), () => {}, {
    api: { SpeechRecognition: Recognition }, defer: f => callbacks.push(f),
  });
  const a = Object.assign([{ transcript: 'one' }], { isFinal: true });
  const b = Object.assign([{ transcript: 'tw' }], { isFinal: false });
  object.onresult({ resultIndex: 0, results: [a, b] });
  object.onresult({ resultIndex: 0, results: [a, b] });
  assert.deepEqual(outputs.filter(e => e[0] === 'final'), [['final', 'one']]);
  assert.ok(outputs.some(e => e[0] === 'interim' && e[1] === 'tw'));
  object.onend();
  callbacks.shift()();
  assert.equal(object.starts, 2);
  recognition.stop();
  assert.equal(callbacks.length, 0);
});
