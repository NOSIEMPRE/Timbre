from __future__ import annotations
import json
import os
from typing import Callable
import anthropic
from timbre import observe, session
from timbre.tools.registry import Tool

_DEFAULT_MODEL = "claude-opus-4-7"


class AnthropicProvider:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = os.getenv("MODEL", _DEFAULT_MODEL)

    async def complete(self, system: str, user: str) -> str:
        import asyncio

        def _call():
            return self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}],
            )

        resp = await asyncio.to_thread(_call)
        session.add_usage(self.model, resp.usage.input_tokens, resp.usage.output_tokens)
        return resp.content[0].text

    async def react_loop(
        self,
        system: str,
        user: str,
        tools: list[Tool],
        send: Callable[[dict], None],
        max_iterations: int = 18,
    ) -> str:
        import asyncio

        tr = observe.trace(name="react_loop", input={"user": user[:200]})
        messages = [{"role": "user", "content": user}]
        anthropic_tools = [t.to_anthropic() for t in tools]
        tool_map = {t.name: t for t in tools}

        for _ in range(max_iterations):
            def _call(msgs=messages):
                return self._client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    system=system,
                    tools=anthropic_tools,
                    messages=msgs,
                )

            resp = await asyncio.to_thread(_call)
            session.add_usage(self.model, resp.usage.input_tokens, resp.usage.output_tokens)
            observe.generation(
                tr, name="llm_call", model=self.model,
                input=messages, output=str(resp.content),
                usage={"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
            )

            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            text_blocks = [b for b in resp.content if b.type == "text"]

            if resp.stop_reason == "end_turn" or not tool_uses:
                observe.flush()
                return text_blocks[0].text if text_blocks else ""

            messages.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for tu in tool_uses:
                send({"type": "tool_start", "name": tu.name})
                tool = tool_map.get(tu.name)
                try:
                    result = await tool.handler(**tu.input) if tool else {"error": f"Unknown tool: {tu.name}"}
                except Exception as e:
                    result = {"error": str(e)}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            messages.append({"role": "user", "content": tool_results})

        observe.flush()
        final = self._client.messages.create(
            model=self.model, max_tokens=8192, system=system,
            messages=messages + [{"role": "user", "content": "请根据以上信息完成输出。"}],
        )
        session.add_usage(self.model, final.usage.input_tokens, final.usage.output_tokens)
        return final.content[0].text if final.content else ""
