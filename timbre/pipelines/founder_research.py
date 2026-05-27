from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable
import yaml

from timbre.providers import get_provider
from timbre.tools import SYNTHESIS_TOOLS
from timbre.tools.web_search import web_search
from timbre.tools.read_file import read_file
from timbre.tools.browse_url import browse_url
from timbre.memory.store import recall

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load(name: str) -> dict:
    with open(_PROMPTS_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fmt(template: str, **kwargs) -> str:
    """Safe substitute: only replaces known {key} tokens, ignores bare { } in JSON examples."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


def _parse_json(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Stage 1: Entity Resolution ────────────────────────────────────────────────

async def resolve_entity(input_text: str, send: Callable) -> dict:
    send({"type": "stage", "name": "entity_resolution", "status": "start", "label": "实体识别中"})

    existing = recall(input_text)
    if existing:
        send({"type": "memory_hit", "entity": existing})

    p = _load("entity_resolution")
    system = _load("system")["role"]
    task = _fmt(p["task"], input=input_text)

    provider = get_provider()
    raw = await provider.react_loop(system=system, user=task, tools=[web_search], send=send, max_iterations=4)

    parsed = _parse_json(raw)
    # Treat parsed result as valid only if at least founder or company is non-null
    if parsed and (parsed.get("founder") or parsed.get("company")):
        entity = parsed
    else:
        entity = {
            "founder": input_text, "founder_en": "", "company": input_text,
            "valuation": "unknown", "confirmed": False, "confidence": "low",
        }
    entity.pop("is_chinese_founder", None)

    send({"type": "stage", "name": "entity_resolution", "status": "done", "result": entity})
    return entity


# ── Stage 2a: Research Plan ───────────────────────────────────────────────────

async def plan_research(entity: dict, send: Callable) -> dict:
    send({"type": "stage", "name": "research_plan", "status": "start", "label": "制定搜索计划"})

    p = _load("research_plan")
    task = _fmt(p["task"],
        founder=entity.get("founder", ""),
        founder_en=entity.get("founder_en", "") or "",
        company=entity.get("company", ""),
        valuation=entity.get("valuation", "unknown"),
    )

    provider = get_provider()
    raw = await provider.complete(system=p["system"], user=task)
    plan = _parse_json(raw) or {"dimensions": []}

    send({"type": "plan_ready", "plan": plan})
    send({"type": "stage", "name": "research_plan", "status": "done"})
    return plan


# ── Stage 2b: Parallel Search ─────────────────────────────────────────────────

async def execute_searches(plan: dict, send: Callable) -> dict:
    send({"type": "stage", "name": "search", "status": "start", "label": "并行搜索中"})

    async def run_query(query: str) -> dict:
        send({"type": "tool_start", "name": "web_search"})
        result = await web_search.handler(query=query)
        return {"query": query, "results": result.get("results", [])}

    tasks, dimension_map = [], {}
    for dim in plan.get("dimensions", []):
        for q in dim.get("queries", []):
            dimension_map[len(tasks)] = dim["name"]
            tasks.append(run_query(q))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    by_dimension: dict[str, list] = {}
    for i, result in enumerate(all_results):
        dim_name = dimension_map.get(i, "misc")
        if dim_name not in by_dimension:
            by_dimension[dim_name] = []
        if not isinstance(result, Exception):
            by_dimension[dim_name].append(result)

    send({"type": "stage", "name": "search", "status": "done"})
    return by_dimension


# ── Stage 3: Synthesis ────────────────────────────────────────────────────────

async def synthesize(entity: dict, results_by_dimension: dict, extra_context: str, send: Callable) -> str:
    send({"type": "stage", "name": "synthesis", "status": "start", "label": "整理搜索结果"})

    # Build numbered source list — every fact must trace back to one of these
    sources: list[dict] = []
    dim_blocks: list[str] = []
    raw_total = 0

    for dim_name, queries in results_by_dimension.items():
        excerpts: list[str] = []
        for q_result in queries:
            for r in q_result.get("results", [])[:4]:
                url = r.get("url", "")
                title = (r.get("title") or "").strip()
                content = (r.get("content") or r.get("snippet") or "").strip()
                raw_total += 1
                if not url:
                    continue
                n = len(sources) + 1
                sources.append({"n": n, "title": title, "url": url})
                body = content[:500] if content else "(摘要不可用，请点击链接查看原文)"
                excerpts.append(
                    f"[{n}] {title}\n来源：{url}\n原文：{body}"
                )
        if excerpts:
            dim_blocks.append(f"### {dim_name}\n\n" + "\n\n".join(excerpts))

    send({"type": "search_summary", "raw": raw_total, "used": len(sources)})

    research_results = "\n\n".join(dim_blocks)
    ref_list = "\n".join(f"[{s['n']}] {s['title']} — {s['url']}" for s in sources)

    p = _load("founder_profile")
    system = _load("system")["role"]
    template = p.get("output_template", "")
    full_task = (
        p["task"]
        + "\n\n按以下模板输出，直接从标题开始：\n\n"
        + template
    )
    task = _fmt(full_task,
        founder=entity.get("founder", ""),
        company=entity.get("company", ""),
        date=datetime.now().strftime("%Y-%m-%d"),
        valuation=entity.get("valuation", "unknown"),
        research_results=research_results,
        ref_list=ref_list,
        extra_context=f"\n### 附加上下文\n\n{extra_context}" if extra_context else "",
    )

    provider = get_provider()
    # Single call only — no ReAct loop, no self-directed browsing
    profile = await provider.complete(system=system, user=task)

    send({"type": "stage", "name": "synthesis", "status": "done"})
    return profile


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_founder_research(
    input_text: str,
    send: Callable,
    context_files: list[str] | None = None,
    context_urls: list[str] | None = None,
) -> dict:
    entity = await resolve_entity(input_text, send)

    extra_parts = []
    for path in (context_files or []):
        send({"type": "stage", "name": "context", "status": "start", "label": f"读取 {path}"})
        result = await read_file.handler(file_path=path)
        if result.get("error"):
            send({"type": "context_error", "path": path, "error": result["error"]})
        else:
            extra_parts.append(f"**文件：{path}**\n\n{result['content']}")
        send({"type": "stage", "name": "context", "status": "done"})

    for url in (context_urls or []):
        send({"type": "stage", "name": "context", "status": "start", "label": f"获取 {url}"})
        result = await browse_url.handler(url=url)
        if result.get("error"):
            send({"type": "context_error", "path": url, "error": result["error"]})
        else:
            extra_parts.append(f"**URL：{url}**\n\n{result['content']}")
        send({"type": "stage", "name": "context", "status": "done"})

    extra_context = "\n\n---\n\n".join(extra_parts)

    plan = await plan_research(entity, send)
    results_by_dimension = await execute_searches(plan, send)
    profile = await synthesize(entity, results_by_dimension, extra_context, send)

    return {"profile": profile, "entity": entity}
