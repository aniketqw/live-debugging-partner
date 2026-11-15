"""Shared types for model adapters in the voice harness simulation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[ToolCall]
    meta: dict
