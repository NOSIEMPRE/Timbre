from __future__ import annotations
"""
timbre/pipelines/sourcing.py
Proactive VC sourcing — discover early-stage (Pre-Seed/Seed) projects
without being given a specific company name.
"""
import asyncio
import json
import re
from typing import Callable

from timbre.providers import get_provider
from timbre.tools.web_search import web_search


# ── Discovery query bank ──────────────────────────────────────────────────────

_BASE_QUERIES = [
    # HackerNews "Show HN" — founders self-announcing
    'site:news.ycombinator.com "Show HN" AI startup 2025',
    'site:news.ycombinator.com "Show HN" developer tool machine learning 2025',
    # YC batch companies
    '"Y Combinator" W25 S25 AI companies founders list',
    'YCombinator 2025 batch artificial intelligence startups',
    # ProductHunt launches
    'ProductHunt new AI startup launched 2025',
    # TechCrunch early-stage
    'site:techcrunch.com "pre-seed" OR "seed" AI startup 2025',
    # Small round announcements
    '"seed round" "$1M" OR "$2M" OR "$3M" OR "$5M" AI 2025 founder',
    '"raised seed" artificial intelligence startup 2025',
    # Founder announcements
    '"we just launched" OR "excited to announce" AI startup 2025',
    '"building in public" AI SaaS 2025 founder',
    # GitHub-originated startups
    '"github" trending AI tool startup open-source 2025',
    # Accelerator demos
    'demo day 2025 AI startup seed pre-seed accelerator',
]

_VERTICAL_EXTRAS: dict[str, list[str]] = {
    "b2b": [
        '"enterprise AI" startup seed 2025 B2B SaaS',
        'vertical SaaS AI startup seed 2025 enterprise software',
    ],
    "infrastructure": [
        'AI infrastructure developer tools seed 2025 startup',
        'MLOps LLMOps infrastructure startup seed 2025',
    ],
    "healthcare": [
        'digital health AI startup seed 2025',
        'healthcare AI startup pre-seed seed 2025',
    ],
    "fintech": [
        'fintech AI startup seed 2025',
        'AI financial services startup early stage 2025',
    ],
    "consumer": [
        'consumer AI app startup seed 2025',
        'AI consumer product launched 2025 seed round',
    ],
}


def _build_queries(theme: str) -> list[str]:
    """Combine base + vertical-specific queries for a given theme."""
    theme_lower = (theme or "").lower().strip()
    extras = _VERTICAL_EXTRAS.get(theme_lower, [])
    if theme and theme_lower not in ("ai", "tech", "科技", "人工智能", ""):
        # Generic theme injection
        extras = extras or [
            f'"{theme}" AI startup seed 2025 early stage',
            f'HackerNews "Show HN" {theme} 2025',
        ]
    return (extras + _BASE_QUERIES)[:14]  # cap total queries


# ── Stage 1: Multi-source discovery ──────────────────────────────────────────

async def discover_projects(theme: str, send: Callable) -> list[dict]:
    """
    Parallel web search across discovery sources.
    Returns a deduplicated list of raw items (title, url, content).
    """
    label = f"多源扫描：{theme}" if theme else "多源扫描（AI / 科技）"
    send({"type": "stage", "name": "sourcing_discover", "status": "start", "label": label})

    queries = _build_queries(theme)

    async def run_query(q: str) -> list:
        send({"type": "tool_start", "name": "web_search"})
        try:
            result = await web_search.handler(query=q)
            return result.get("results", [])
        except Exception:
            return []

    all_results = await asyncio.gather(*[run_query(q) for q in queries])

    seen_urls: set[str] = set()
    raw_items: list[dict] = []
    for results in all_results:
        for r in results[:5]:
            url = r.get("url", "")
            content = (r.get("content") or "").strip()
            title = (r.get("title") or "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw_items.append({"title": title, "url": url, "content": content[:600]})

    send({"type": "stage", "name": "sourcing_discover", "status": "done"})
    send({"type": "sourcing_raw", "count": len(raw_items), "queries": len(queries)})
    return raw_items


# ── Stage 2: LLM extraction + scoring ────────────────────────────────────────

_EXTRACT_SYSTEM = (
    "你是一级市场投资分析师，专注 Pre-Seed/Seed 阶段科技创业项目的主动发现。"
    "只输出纯 JSON，不输出任何其他内容。"
)

_EXTRACT_TASK = """
从以下搜索结果原文中，识别并提取值得一级市场关注的早期创业项目。
{theme_hint}

筛选标准（严格执行）：
1. 成立时间 2022 年至今，处于 Pre-Seed、Seed 或尚未融资阶段
2. 有技术壁垒或差异化切入点（避免 me-too 产品）
3. 有至少一位可识别的创始人姓名
4. 排除：已上市公司、大型科技公司子项目、知名独角兽

搜索结果原文（共 {n} 条，已编号）：

{combined}

---

只输出纯 JSON，最多 12 个项目，只能基于以上原文，禁止编造：
{{"projects": [
  {{
    "name": "公司名（英文优先）",
    "founder": "创始人姓名（搜索结果中已出现则填，否则填 unknown）",
    "one_liner": "一句话产品描述（≤30字）",
    "stage": "Pre-Seed / Seed / Bootstrapped / unknown",
    "founded_year": "成立年份或 unknown",
    "market": "目标市场/赛道（简短）",
    "signals": ["牵引力信号1", "信号2"],
    "source_url": "原文 URL",
    "vc_appeal": "高 / 中 / 低",
    "why": "一句话说明投资吸引力或风险（≤30字）"
  }}
]}}
"""


async def filter_and_rank(raw_items: list[dict], theme: str, send: Callable) -> list[dict]:
    """
    LLM reads raw search excerpts and extracts structured startup records.
    Sorted by vc_appeal (高 first).
    """
    send({"type": "stage", "name": "sourcing_filter", "status": "start", "label": "AI 提取与评分"})

    if not raw_items:
        send({"type": "stage", "name": "sourcing_filter", "status": "done"})
        return []

    excerpts = []
    for i, item in enumerate(raw_items[:30], 1):
        excerpts.append(f"[{i}] {item['title']}\n{item['url']}\n{item['content'][:400]}")
    combined = "\n\n---\n\n".join(excerpts)

    theme_hint = f"重点领域：{theme}" if theme and theme.lower() not in ("ai", "tech") else "领域：AI / 科技"

    task = _EXTRACT_TASK.format(
        theme_hint=theme_hint,
        n=len(raw_items[:30]),
        combined=combined,
    )

    provider = get_provider()
    raw = await provider.complete(system=_EXTRACT_SYSTEM, user=task)

    send({"type": "stage", "name": "sourcing_filter", "status": "done"})

    raw_clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
    m = re.search(r"\{.*\}", raw_clean, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group())
        projects = data.get("projects", [])
    except json.JSONDecodeError:
        return []

    # Sort: 高 > 中 > 低 > unknown
    appeal_order = {"高": 0, "中": 1, "低": 2}
    projects.sort(key=lambda p: appeal_order.get(str(p.get("vc_appeal", "")), 3))
    return projects


# ── Stage 2.5: Targeted founder lookup ───────────────────────────────────────

_FOUNDER_PATTERNS = [
    # "Founded by Jane Smith", "Co-founded by Jane Smith"
    r'(?:co-?)?founded\s+by\s+([A-Z][a-zÀ-ž\'-]+(?:\s+[A-Z][a-zÀ-ž\'-]+)+)',
    # "CEO Jane Smith", "CEO: Jane Smith"
    r'\bCEO[:\s]+([A-Z][a-zÀ-ž\'-]+(?:\s+[A-Z][a-zÀ-ž\'-]+)+)',
    # "Jane Smith, CEO" or "Jane Smith, founder"
    r'([A-Z][a-zÀ-ž\'-]+(?:\s+[A-Z][a-zÀ-ž\'-]+)+),\s+(?:CEO|founder|co-founder)',
    # "by Jane Smith" near startup/launch context
    r'\bby\s+([A-Z][a-zÀ-ž]+\s+[A-Z][a-zÀ-ž]+)',
]

# Common false positives to reject
_NOISE_NAMES = {
    "Show HN", "Hacker News", "Y Combinator", "Product Hunt", "Tech Crunch",
    "Angel List", "Crunch Base", "Seed Round", "Series A", "Demo Day",
    "New York", "San Francisco", "Silicon Valley", "United States",
}

# Company-name suffixes — if a "founder name" ends with these, it's a false positive
_COMPANY_SUFFIXES = re.compile(
    r'\b(AI|Inc|Ltd|LLC|Corp|Labs|Technologies|Tech|Studio|Studios|Health|'
    r'Cloud|Capital|Ventures|Platform|Platforms|Software|Systems)\b',
    re.IGNORECASE,
)

# Noise fragments that appear in sentences (not names)
_SENTENCE_FRAGMENTS = re.compile(
    r'\b(told|said|says|announced|joined|founded|built|launched|raised|'
    r'for|at|and|the|our|his|her|their|who|is|are|was|were)\b',
    re.IGNORECASE,
)


_MONTHS = {
    "Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec",
    "January","February","March","April","June","July","August",
    "September","October","November","December",
}

# Single common English words that look capitalized but aren't names
_COMMON_WORDS = {
    "The","This","That","These","Those","With","From","Into","Over",
    "Under","About","After","Before","Since","Until","While","When",
    "Where","Which","What","That","There","Their","They","Them",
    "Also","Just","More","Most","Some","Such","Each","Both","Many",
    "Other","Same","Next","Last","First","New","Old","Big","Small",
    "Good","Best","Top","High","Low","Now","Then","Here",
}


def _clean_candidate(raw: str) -> str:
    """
    Validate and clean a raw regex match into a proper personal name.
    Returns empty string if it doesn't look like a real name.
    """
    # Take only first 2–3 tokens (first + last [+ middle])
    parts = raw.strip().split()[:3]

    # Must be exactly 2–3 words
    if len(parts) < 2:
        return ""

    # Reject month names and common English words in any position
    for part in parts:
        if part in _MONTHS or part in _COMMON_WORDS:
            return ""

    name = " ".join(parts)

    # Reject if any part looks like a sentence fragment or company suffix
    if _SENTENCE_FRAGMENTS.search(name):
        return ""
    if _COMPANY_SUFFIXES.search(name):
        return ""

    # Each part should look like a proper noun:
    # - starts with uppercase
    # - only letters (+ apostrophe / hyphen for names like O'Brien, Al-Hassan)
    # - at least 2 chars
    for part in parts:
        core = re.sub(r"['-]", "", part)
        if not core.isalpha() or len(core) < 2:
            return ""
        if not part[0].isupper():
            return ""

    # Reject known noise strings
    if name in _NOISE_NAMES:
        return ""

    return name


async def _lookup_founder(company: str, send: Callable) -> str:
    """One targeted search to find a founder name for a company."""
    send({"type": "tool_start", "name": "web_search"})
    try:
        result = await web_search.handler(
            query=f'"{company}" founder CEO co-founder site:linkedin.com OR site:crunchbase.com OR site:techcrunch.com'
        )
        snippets = " ".join(
            r.get("content", "") + " " + r.get("title", "")
            for r in result.get("results", [])[:5]
        )
        for pattern in _FOUNDER_PATTERNS:
            for m in re.finditer(pattern, snippets, re.IGNORECASE):
                name = _clean_candidate(m.group(1))
                if name:
                    return name
    except Exception:
        pass
    return ""


async def enrich_founders(projects: list[dict], send: Callable) -> list[dict]:
    """
    Stage 2.5 — For projects where founder == 'unknown' or empty,
    run one targeted web search to find the founder name.
    Runs in parallel, capped at 8 concurrent lookups.
    """
    unknown_idx = [
        i for i, p in enumerate(projects)
        if not p.get("founder") or p.get("founder", "").lower() in ("unknown", "未知", "")
    ]

    if not unknown_idx:
        return projects

    send({
        "type": "stage", "name": "founder_lookup", "status": "start",
        "label": f"补全创始人信息（{len(unknown_idx)} 个项目）"
    })

    # Limit concurrency to avoid rate limits
    sem = asyncio.Semaphore(8)

    async def lookup_one(idx: int) -> tuple[int, str]:
        async with sem:
            company = projects[idx].get("name", "")
            if not company:
                return idx, ""
            name = await _lookup_founder(company, send)
            return idx, name

    results = await asyncio.gather(*[lookup_one(i) for i in unknown_idx])

    found_count = 0
    for idx, name in results:
        if name:
            projects[idx]["founder"] = name
            found_count += 1

    send({
        "type": "stage", "name": "founder_lookup", "status": "done",
        "found": found_count, "total": len(unknown_idx)
    })
    return projects


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_sourcing(theme: str, send: Callable) -> list[dict]:
    """
    Proactive VC sourcing pipeline.

    1. Discover: parallel search across HN / PH / TC / YC / GitHub / announcements
    2. Filter:   LLM extracts + scores each project for VC relevance
    2.5 Enrich:  targeted founder lookup for unknown entries
    3. Return:   ranked list sorted by vc_appeal

    Args:
        theme: optional vertical focus (e.g. "B2B", "healthcare", "infrastructure")
        send:  event callback for CLI display

    Returns:
        List of project dicts with keys: name, founder, one_liner, stage,
        founded_year, market, signals, source_url, vc_appeal, why
    """
    raw_items = await discover_projects(theme, send)
    projects = await filter_and_rank(raw_items, theme, send)
    projects = await enrich_founders(projects, send)
    return projects
