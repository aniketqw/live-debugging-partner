"""Interface shared by the scripted and optional Ollama adapters."""

from typing import Protocol

from vh.types import ModelResponse


class ModelAdapter(Protocol):
    name: str

    def respond(self, messages: list[dict], tools: list[dict]) -> ModelResponse: ...
