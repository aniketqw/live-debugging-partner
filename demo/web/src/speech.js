const browserScope = () => globalThis;

export function completedWords(text, index) {
  const completed = [...text.matchAll(/\S+/g)].filter(match =>
    match.index + match[0].length <= index).map(match => match[0]);
  return { spoken_prefix: completed.join(' '), n_words: completed.length };
}

export function recognitionAvailable(api = browserScope()) {
  return Boolean(api.SpeechRecognition || api.webkitSpeechRecognition);
}

export function startRecognition(lang, onInterim, onFinal, onEnd, {
  api = browserScope(), defer = fn => setTimeout(fn, 300), onError = () => {},
} = {}) {
  const Recognition = api.SpeechRecognition || api.webkitSpeechRecognition;
  if (!Recognition) return null;
  const recognition = new Recognition();
  recognition.lang = lang;
  recognition.continuous = true;
  recognition.interimResults = true;
  let active = true;
  const seen = new Set();
  const resume = () => {
    if (!active) return;
    seen.clear();
    try { recognition.start(); }
    catch { active = false; onError('start-failed'); onEnd(); }
  };
  recognition.onresult = event => {
    if (!active) return;
    const interim = [];
    const final = [];
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const transcript = result[0]?.transcript.trim();
      if (result.isFinal) {
        if (!seen.has(i)) {
          seen.add(i);
          if (transcript) final.push(transcript);
        }
      } else if (transcript) interim.push(transcript);
    }
    onInterim(interim.join(' '));
    if (final.length) onFinal(final.join(' '));
  };
  recognition.onerror = event => {
    if (!active || ['aborted', 'no-speech'].includes(event.error)) return;
    active = false;
    onError(event.error);
    onEnd();
  };
  recognition.onend = () => {
    if (active) {
      onInterim('');
      defer(resume);
    }
  };
  resume();
  return {
    stop() {
      if (!active) return;
      active = false;
      recognition.abort();
      onEnd();
    },
    get active() { return active; },
  };
}

export function createSpeaker(api = browserScope()) {
  let current = null;
  const supported = Boolean(api.speechSynthesis && api.SpeechSynthesisUtterance);
  return {
    supported,
    speak(text, { lang = 'en-IN', onBoundary = () => {}, onEnd = () => {}, onError = () => {} } = {}) {
      if (!supported) return false;
      const utterance = new api.SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      const speech = { text, boundary: 0 };
      current = speech;
      utterance.onboundary = event => {
        if (current !== speech || (event.name && event.name !== 'word')) return;
        if (!Number.isInteger(event.charIndex)) return;
        speech.boundary = Math.max(speech.boundary, Math.min(event.charIndex, text.length));
        onBoundary(completedWords(text, speech.boundary));
      };
      utterance.onend = () => {
        if (current !== speech) return;
        current = null;
        onEnd();
      };
      utterance.onerror = event => {
        if (current !== speech) return;
        current = null;
        onError(event.error);
      };
      try { api.speechSynthesis.speak(utterance); }
      catch {
        current = null;
        return false;
      }
      return true;
    },
    cancel() {
      const before = current;
      current = null;
      if (before) api.speechSynthesis.cancel();
      return before ? completedWords(before.text, before.boundary) : { spoken_prefix: '', n_words: 0 };
    },
  };
}
