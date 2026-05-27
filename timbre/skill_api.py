"""
timbre/skill_api.py — Timbre VC Intelligence Skill
Anthropic API-compatible tool definitions + async handlers.

Drop-in usage with the Anthropic Python SDK:

    from timbre.skill_api import TOOLS, dispatch_tool_call

    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        tools=TOOLS,
        messages=[{"role": "user", "content": "帮我找最近值得关注的早期 AI 项目"}],
    )

    for block in response.content:
        if block.type == "tool_use":
            result = await dispatch_tool_call(block.name, block.input)

See example_claude_api.py for a complete agentic loop.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

# ── Auto-load .env so the Skill works standalone ─────────────────────────────
try:
    from dotenv import load_dotenv

    load_dotenv(Path.home() / ".timbre" / ".env")
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; rely on environment variables being set

# ── Tool schemas (Anthropic input_schema format) ──────────────────────────────

VC_SOURCING_TOOL: dict[str, Any] = {
    "name": "vc_sourcing",
    "description": (
        "主动发现早期（Pre-Seed / Seed）科技创业项目，无需提前知道公司名称。"
        " 并行扫描 HackerNews Show HN、YC 批次、ProductHunt、TechCrunch、"
        " 种子轮融资公告、创始人自发布、GitHub 热门项目及加速器 Demo Day 等来源，"
        " 提取结构化项目记录并按 VC 吸引力（高/中/低）排序。\n\n"
        "Use this tool when the user wants to proactively discover new startups "
        "without naming a specific company — e.g. 'find early-stage AI companies', "
        "'帮我找最近值得关注的早期项目', 'sourcing healthcare AI', 'pre-seed B2B SaaS'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "theme": {
                "type": "string",
                "description": (
                    "Optional vertical or technology focus. Examples: 'AI infrastructure', "
                    "'healthcare', 'B2B SaaS', 'fintech', 'consumer'. "
                    "Leave empty for a broad AI/tech scan."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of projects to return (1–12). Default: 10.",
                "minimum": 1,
                "maximum": 12,
            },
        },
        "required": [],
    },
}

FOUNDER_RESEARCH_TOOL: dict[str, Any] = {
    "name": "founder_research",
    "description": (
        "Deep-dive VC due-diligence research on a specific founder or startup. "
        "Produces a structured Markdown profile with:\n"
        "  • 创始人画像 (background, education, career, public statements)\n"
        "  • 创始团队 (co-founders, team size)\n"
        "  • 产品与商业模式 (product, business model, moat, competitors)\n"
        "  • 业务牵引力 (ARR/MRR, users, growth, key customers)\n"
        "  • 融资信息 (funding rounds with investor wiki-links)\n"
        "  • 投资亮点与主要顾虑 (P0/P1/P2 risk signals)\n"
        "  • 近期动态 (chronological events with citations)\n\n"
        "All facts are source-anchored with [N] citations. "
        "Missing public data is marked '暂无公开数据' — never fabricated.\n\n"
        "Use this tool when the user names a founder or company to research, "
        "e.g. 'research Clay CEO', 'Kareem Amin', '调研 Figma 的创始人'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Founder name, company name, or both. "
                    "Examples: 'Kareem Amin Clay', 'Dylan Field Figma', "
                    "'Clay CRM', '段誉 清华 AI startup'."
                ),
            },
            "context_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of URLs to read before synthesizing "
                    "(e.g. company website, deck PDF, Crunchbase page)."
                ),
            },
            "save_to_vault": {
                "type": "boolean",
                "description": (
                    "If true (default), save the Markdown profile to the "
                    "Obsidian vault / ~/.timbre/profiles/. Set false to return "
                    "the profile text only without writing to disk."
                ),
            },
        },
        "required": ["query"],
    },
}

# Exported list — pass directly to `tools=` in client.messages.create()
TOOLS: list[dict[str, Any]] = [VC_SOURCING_TOOL, FOUNDER_RESEARCH_TOOL]


# ── Silent event sink (used internally when no UI callback is provided) ───────

def _noop(_event: dict) -> None:
    """Default send callback: silently discard pipeline events."""


# ── Tool handlers ─────────────────────────────────────────────────────────────


async def _handle_vc_sourcing(
    theme: str = "",
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Runs the proactive VC sourcing pipeline and returns structured results.

    Returns a dict with:
        projects: list of up to max_results project records
        theme:    the vertical that was scanned
        count:    number of projects found
    """
    from timbre.pipelines.sourcing import run_sourcing

    projects = await run_sourcing(theme=theme or "", send=_noop)
    projects = projects[:max_results]

    return {
        "theme": theme or "AI / 科技（综合）",
        "count": len(projects),
        "projects": projects,
    }


async def _handle_founder_research(
    query: str,
    context_urls: list[str] | None = None,
    save_to_vault: bool = True,
) -> dict[str, Any]:
    """
    Runs the full founder research pipeline and returns the Markdown profile.

    Returns a dict with:
        founder:  resolved founder name
        company:  resolved company name
        profile:  full Markdown VC due-diligence profile
        saved_to: path where the profile was saved (or None)
        quality:  quality score dict {score, word_count, url_count, issues}
    """
    import os
    import re
    from datetime import datetime
    from timbre.pipelines.founder_research import run_founder_research
    from timbre.eval.quality_check import quality_check

    def _collect(event: dict) -> None:
        pass  # discard progress events in API mode

    result = await run_founder_research(
        input_text=query,
        context_urls=context_urls or [],
        send=_collect,
    )

    profile = result.get("profile", "")
    entity = result.get("entity", {})
    founder = entity.get("founder", "")
    company = entity.get("company", "")

    metrics = quality_check(profile, entity)
    saved_to: str | None = None

    if save_to_vault and profile:
        vault = os.getenv("OBSIDIAN_VAULT_PATH")
        subfolder = os.getenv("OBSIDIAN_SUBFOLDER", "Timbre")
        if vault:
            output_dir = Path(vault) / subfolder
        else:
            output_dir = Path.home() / ".timbre" / "profiles"
        output_dir.mkdir(parents=True, exist_ok=True)

        date = datetime.now().strftime("%Y-%m-%d")

        def _slugify(s: str) -> str:
            return re.sub(r"[^\w一-鿿-]", "", str(s).lower().replace(" ", "-"))[:60]

        f_slug = _slugify(entity.get("founder_en") or founder or "unknown")
        c_slug = _slugify(company or "unknown")
        filename = f"{f_slug}-{c_slug}-{date}.md"
        filepath = output_dir / filename

        # Add a minimal YAML front-matter for Obsidian
        lines = ["---"]
        if founder and founder != company:
            lines.append(f'founder: "{founder}"')
        lines.append(f'company: "{company}"')
        lines += [
            f"created: {date}",
            'tags: ["founder-profile"]',
            'source: "见微·Timbre"',
            "---", "",
        ]
        frontmatter = "\n".join(lines)

        # Wrap first occurrence of company name in Obsidian wiki-link
        profile_linked = re.sub(
            rf"(?<!\[\[)\b{re.escape(company)}\b(?!\]\])",
            f"[[{company}]]",
            profile,
            count=1,
        ) if company and len(company) >= 2 else profile

        filepath.write_text(frontmatter + profile_linked, encoding="utf-8")
        saved_to = str(filepath)

    return {
        "founder": founder,
        "company": company,
        "profile": profile,
        "saved_to": saved_to,
        "quality": metrics,
    }


# ── Main dispatcher ───────────────────────────────────────────────────────────


async def dispatch_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """
    Route a tool_use block from the Claude API to the correct handler.

    Usage:
        for block in response.content:
            if block.type == "tool_use":
                result = await dispatch_tool_call(block.name, block.input)
                # Append result as tool_result message in the next turn

    Returns a dict that should be JSON-serialised and passed back to the API
    as the content of a tool_result message.
    """
    if tool_name == "vc_sourcing":
        return await _handle_vc_sourcing(**tool_input)
    elif tool_name == "founder_research":
        return await _handle_founder_research(**tool_input)
    else:
        return {"error": f"Unknown tool: {tool_name!r}"}


# ── Synchronous convenience wrapper ──────────────────────────────────────────


def dispatch_tool_call_sync(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Synchronous version of dispatch_tool_call for non-async callers."""
    return asyncio.run(dispatch_tool_call(tool_name, tool_input))


# ── Minimal self-test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("Timbre Skill API — tool definitions loaded ✓")
    print(f"  Registered tools: {[t['name'] for t in TOOLS]}")
    print()
    print("VC_SOURCING_TOOL input_schema:")
    print(json.dumps(VC_SOURCING_TOOL["input_schema"], indent=2, ensure_ascii=False))
    print()
    print("FOUNDER_RESEARCH_TOOL input_schema:")
    print(json.dumps(FOUNDER_RESEARCH_TOOL["input_schema"], indent=2, ensure_ascii=False))

    if "--run-sourcing" in sys.argv:
        print("\nRunning live sourcing test (requires TAVILY_API_KEY)...")
        result = asyncio.run(_handle_vc_sourcing(theme="AI infrastructure", max_results=3))
        print(json.dumps(result, indent=2, ensure_ascii=False))
