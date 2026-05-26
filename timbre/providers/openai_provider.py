from __future__ import annotations
import json
import os
from typing import Callable
from openai import AsyncOpenAI
from timbre import observe
from timbre.tools.registry import Tool


class OpenAIProvider:
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.getenv("MODEL", "gpt-4o")

    async def complete(self, system: str, user: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def react_loop(
        self,
        system: str,
        user: str,
        tools: list[Tool],
        send: Callable[[dict], None],
        max_iterations: int = 18,
    ) -> str:
        tr = observe.trace(name="react_loop", input={"user": user[:200]})
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        openai_tools = [t.to_openai() for t in tools]
        tool_map = {t.name: t for t in tools}

        for _ in range(max_iterations):
            resp = await self._client.chat.completions.create(
                model=self.model, max_tokens=8192,
                messages=messages, tools=openai_tools, tool_choice="auto",
            )
            choice = resp.choices[0]
            observe.generation(
                tr, name="llm_call", model=self.model,
                input=messages, output=choice.message.content or "",
                usage={"input": resp.usage.prompt_tokens, "output": resp.usage.completion_tokens}
                if resp.usage else None,
            )

            if choice.finish_reason == "stop" or not choice.message.tool_calls:
                observe.flush()
                return choice.message.content or ""

            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                send({"type": "tool_start", "name": tc.function.name})
                tool = tool_map.get(tc.function.name)
                try:
                    args = json.loads(tc.function.arguments)
                    result = await tool.handler(**args) if tool else {"error": f"Unknown tool: {tc.function.name}"}
                except Exception as e:
                    result = {"error": str(e)}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        observe.flush()
        resp = await self._client.chat.completions.create(
            model=self.model, max_tokens=8192,
            messages=messages + [{"role": "user", "content": "请根据以上信息完成输出。"}],
        )
        return resp.choices[0].message.content or ""
