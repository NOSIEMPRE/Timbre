from __future__ import annotations
from typing import Protocol, AsyncIterator, Callable, Any
from tools.registry import Tool


class Provider(Protocol):
    async def react_loop(
        self,
        system: str,
        user: str,
        tools: list[Tool],
        send: Callable[[dict], None],
        max_iterations: int = 18,
    ) -> str: ...

    async def complete(self, system: str, user: str) -> str: ...
