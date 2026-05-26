from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., Awaitable[Any]]

    def to_anthropic(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


RESEARCH_TOOLS: list[Tool] = []
SYNTHESIS_TOOLS: list[Tool] = []


def register(tool: Tool, *, synthesis_only: bool = False) -> None:
    if synthesis_only:
        SYNTHESIS_TOOLS.append(tool)
    else:
        RESEARCH_TOOLS.append(tool)
