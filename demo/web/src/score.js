export function validSpeakerCode(code) {
  return /^[A-Za-z][0-9]{0,2}$/.test(code);
}

export function createScoringArm() {
  let armed = null;
  return {
    arm(options) {
      if (!options.sessionId || !options.scenario || !validSpeakerCode(options.speaker_label)) {
        throw new Error('Choose a script, a session, and a valid speaker code.');
      }
      armed = { ...options };
    },
    clear() { armed = null; },
    take(sessionId, source, transcript) {
      if (source !== 'speech' || !armed || armed.sessionId !== sessionId) return null;
      const { scenario, speaker_label } = armed;
      armed = null;
      return { scenario, speaker_label, transcript, source, consent: true };
    },
  };
}
