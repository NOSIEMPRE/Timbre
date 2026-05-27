from __future__ import annotations
import asyncio
import json
import re
from typing import Callable

from timbre.providers import get_provider
from timbre.tools.web_search import web_search


async def research_investor_portfolio(investor: str, send: Callable) -> list[dict]:
    """Search for an investor's AI/tech startup portfolio and return a structured list."""
    send({"type": "stage", "name": "investor_search", "status": "start",
          "label": f"搜索 {investor} 投资组合"})

    queries = [
        f'"{investor}" portfolio AI startup companies 2024 2025',
        f'"{investor}" investments artificial intelligence funding rounds',
        f'"{investor}" AI companies invested crunchbase pitchbook',
        f'"{investor}" portfolio tech startups list recent',
    ]

    async def run_query(q: str) -> list:
        send({"type": "tool_start", "name": "web_search"})
        try:
            result = await web_search.handler(query=q)
            return result.get("results", [])
        except Exception:
            return []

    all_results = await asyncio.gather(*[run_query(q) for q in queries])

    # Collect and deduplicate by URL
    seen_urls: set[str] = set()
    snippets: list[str] = []
    for results in all_results:
        for r in results[:5]:
            url = r.get("url", "")
            content = (r.get("content") or "").strip()[:500]
            title = (r.get("title") or "").strip()
            if url and content and url not in seen_urls:
                seen_urls.add(url)
                snippets.append(f"[{title}]({url})\n{content}")

    send({"type": "stage", "name": "investor_search", "status": "done"})

    if not snippets:
        return []

    send({"type": "stage", "name": "investor_extract", "status": "start", "label": "提取投资组合"})

    combined = "\n\n---\n\n".join(snippets[:16])
    provider = get_provider()
    raw = await provider.complete(
        system="你是数据提取助手，只输出纯 JSON，不输出任何其他内容。",
        user=(
            f"从以下搜索结果中，提取 {investor} 投资过的 AI 或科技创业公司列表。\n\n"
            f"{combined}\n\n"
            "只输出如下格式的纯 JSON，最多 15 家，只包含搜索结果中真实出现的公司，不得编造：\n"
            '{"companies": ['
            '{"name": "公司名", "description": "一句话描述", '
            '"stage": "融资轮次或 unknown", "amount": "融资金额或 unknown", "year": "年份或 unknown"}'
            "]}"
        ),
    )

    send({"type": "stage", "name": "investor_extract", "status": "done"})

    raw_clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
    m = re.search(r"\{.*\}", raw_clean, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            return data.get("companies", [])
        except json.JSONDecodeError:
            pass
    return []
