"""Word timing for the voice simulation; produces no audio."""

from ldp.model import Params


class MockTTS:
    def __init__(self, params: Params):
        self.params = params

    def speak(self, text: str, start_ms: int) -> tuple[int, list[tuple[str, int, int]]]:
        """Return the end time and a span for each whitespace-delimited word."""
        duration = self.params.tts_ms_per_word
        words = [
            (word, start_ms + index * duration, start_ms + (index + 1) * duration)
            for index, word in enumerate(text.split())
        ]
        return start_ms + len(words) * duration, words

    def cut(self, words: list[tuple[str, int, int]], cut_ms: int) -> tuple[str, int]:
        """Return only the fully spoken prefix, with normalized whitespace."""
        complete = []
        for word, _, end_ms in words:
            if end_ms > cut_ms:
                break
            complete.append(word)
        return " ".join(complete), len(complete)
