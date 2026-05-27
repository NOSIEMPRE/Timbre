#!/usr/bin/env python3
"""
example_claude_api.py — Timbre Skill: minimal Claude API integration example

Demonstrates how to embed the vc_sourcing and founder_research tools in any
Claude API application using the Anthropic Python SDK.

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    export TAVILY_API_KEY=tvly-...

Usage:
    python example_claude_api.py
    python example_claude_api.py "帮我找最近值得关注的早期 AI infrastructure 项目"
    python example_claude_api.py "研究 Figma 的创始人 Dylan Field"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import anthropic

from timbre.skill_api import TOOLS, dispatch_tool_call

# ---------------------------------------------------------------------------
# Helper: run the full tool-use agentic loop
# ---------------------------------------------------------------------------

async def run_agent(user_message: str) -> str:
    """
    Send a message to Claude with Timbre tools attached and execute any
    tool calls until Claude returns a final text response.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict] = [{"role": "user", "content": user_message}]

    system = (
        "你是一名专注于一级市场投资的 AI 分析助手，名为「见微·Timbre」。\n"
        "你有两个工具可以使用：\n"
        "  • vc_sourcing — 主动发现早期（Pre-Seed/Seed）创业项目，无需提前知道公司名称\n"
        "  • founder_research — 对指定创始人或公司进行深度 VC 尽调，生成结构化档案\n\n"
        "用户提问时，判断是否需要调用工具获取信息，然后基于工具返回的数据给出专业、简洁的分析。\n"
        "工具结果中的 profile 字段包含完整 Markdown 档案，可直接引用关键段落。"
    )

    print(f"\n── 用户 ──\n{user_message}\n")

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Collect tool_use blocks and text blocks
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        # No more tool calls — return final text
        if response.stop_reason == "end_turn" or not tool_use_blocks:
            final_text = text_blocks[0].text if text_blocks else ""
            print(f"── 助手 ──\n{final_text}\n")
            return final_text

        # Append assistant turn (full content blocks, not just text)
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool call in parallel
        tool_results = []
        for block in tool_use_blocks:
            print(f"  ⚙  调用工具：{block.name}({json.dumps(block.input, ensure_ascii=False)})")
            result = await dispatch_tool_call(block.name, block.input)

            # Summarise for the console without printing the full profile text
            if block.name == "vc_sourcing":
                count = result.get("count", 0)
                theme = result.get("theme", "")
                print(f"     → 找到 {count} 个项目（领域：{theme}）")
            elif block.name == "founder_research":
                q = result.get("quality", {})
                saved = result.get("saved_to")
                print(
                    f"     → {result.get('founder', '')} / {result.get('company', '')} "
                    f"质量分：{q.get('score', '?')}"
                    + (f"  已保存：{saved}" if saved else "")
                )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# Multi-turn demo: sourcing → drill-down
# ---------------------------------------------------------------------------

async def demo_sourcing_then_research():
    """Show vc_sourcing followed by founder_research on the top result."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "你是「见微·Timbre」，一名专注早期投资的 AI 分析助手。"
        "先用 vc_sourcing 工具发现项目，然后用 founder_research 工具深研第一名项目的创始人。"
    )

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "帮我找最近值得关注的早期 AI infrastructure 项目，"
                "然后深研排名第一的那个项目的创始人。"
            ),
        }
    ]

    print("\n═══ 演示：主动发现 → 深度研究 ═══\n")

    rounds = 0
    while rounds < 5:
        rounds += 1
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        texts = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn" or not tool_uses:
            final = texts[0].text if texts else ""
            print(f"── 最终分析 ──\n{final}\n")
            break

        messages.append({"role": "assistant", "content": response.content})

        results = []
        for tu in tool_uses:
            print(f"  ⚙  {tu.name}({json.dumps(tu.input, ensure_ascii=False)})")
            r = await dispatch_tool_call(tu.name, tu.input)
            if tu.name == "vc_sourcing":
                print(f"     → {r.get('count', 0)} 个项目")
                # Print project names for visibility
                for p in r.get("projects", []):
                    icon = {"高": "▲", "中": "●", "低": "▽"}.get(p.get("vc_appeal", ""), "·")
                    print(f"       {icon} {p.get('name', '')} — {p.get('one_liner', '')}")
            elif tu.name == "founder_research":
                q = r.get("quality", {})
                print(f"     → 质量分 {q.get('score', '?')}，档案 {q.get('word_count', '?')} 字")
                if r.get("saved_to"):
                    print(f"       已保存至 {r['saved_to']}")

            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(r, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": results})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        user_msg = " ".join(sys.argv[1:])
        asyncio.run(run_agent(user_msg))
    else:
        # Run the showcase demo when called with no arguments
        asyncio.run(demo_sourcing_then_research())


if __name__ == "__main__":
    main()
