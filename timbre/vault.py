"""
timbre/vault.py
Obsidian vault structure management — implements the Karpathy LLM-wiki pattern
adapted for VC founder intelligence.

Vault layout (under OBSIDIAN_VAULT_PATH/Timbre/ or ~/.timbre/profiles/):

    Timbre/
    ├── SCHEMA.md       ← How the wiki works (human + LLM readable)
    ├── index.md        ← Master catalog (auto-maintained, one row per founder)
    ├── log.md          ← Append-only activity record
    ├── founders/       ← Founder due-diligence profiles
    ├── investors/      ← Investor entity pages (auto-created from profiles)
    └── sectors/        ← Sector / theme concept pages

Key insight from Karpathy's pattern:
  The LLM should maintain the wiki, not you. Every research session writes to
  multiple pages: a founder profile, zero or more investor pages, a sector page,
  and the index + log. After 20 sessions, Graph View surfaces patterns that no
  single search can find — which investor appears across the most profiles, which
  sector is receiving overlapping bets.
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

# ── Vault folder layout ───────────────────────────────────────────────────────

SUBFOLDERS = ["founders", "investors", "sectors"]

_SCHEMA = """\
---
type: schema
source: "见微·Timbre"
---

# Timbre Knowledge Schema

> This vault is maintained by [见微·Timbre](https://github.com/NOSIEMPRE/Timbre).
> Do not manually reorganize sub-folders — the agent manages structure.
> You can freely edit any page's content; the agent will preserve your edits.

---

## Folder Layout

```
Timbre/
├── SCHEMA.md        ← This file
├── index.md         ← Master catalog (auto-maintained, one row per founder)
├── log.md           ← Activity log (append-only)
├── founders/        ← Founder due-diligence profiles (8-section, [N]-cited)
├── investors/       ← Investor entity pages (auto-created from profiles)
└── sectors/         ← Sector / theme concept pages (auto-created)
```

## Node Types

| Type | Location | Created by |
|------|----------|-----------|
| Founder profile | `founders/` | `founder-research` |
| Investor entity | `investors/` | Auto-extracted from investor names in profiles |
| Sector concept | `sectors/` | Auto-created from founder's market / industry field |

## Cross-linking Conventions

- Company names in index.md → `[[Mastra]]`, `[[ElevenLabs]]`
- Investor pages → `investors/Sequoia.md`, `investors/a16z.md`, etc.
- Sector pages → `sectors/AI-Infrastructure.md`
- All index/log pages link back to each other via `[[index]]` and `[[log]]`

## Operations (ask Claude Code in this vault)

```
query: which investors appear across the most founder profiles?
query: what do all the AI Infrastructure founders have in common?
lint:  find all [[wikilinks]] that have no corresponding page
lint:  identify contradictions between founder profiles
update: re-synthesize the Sequoia investor page from all profiles
```
"""


def ensure_vault_structure(vault_dir: Path) -> None:
    """
    Idempotent. Creates Timbre sub-folder layout and writes SCHEMA.md on first run.
    Call this before every profile save — it's safe to call repeatedly.
    """
    for sub in SUBFOLDERS:
        (vault_dir / sub).mkdir(parents=True, exist_ok=True)

    schema_path = vault_dir / "SCHEMA.md"
    if not schema_path.exists():
        schema_path.write_text(_SCHEMA, encoding="utf-8")


# ── index.md ──────────────────────────────────────────────────────────────────

_INDEX_HEADER = """\
---
type: index
source: "见微·Timbre"
---

# Timbre Index

> Master catalog — auto-maintained by 见微·Timbre.
> See [[log]] for activity history · [[SCHEMA]] for vault layout.

| Company | Founder | Sector | Valuation | Researched |
|---------|---------|--------|-----------|------------|
"""


def update_index(vault_dir: Path, entity: dict, filename: str) -> None:
    """
    Upsert one catalog row in index.md.
    If the company already has a row, replace it (handles re-research + updates).

    Note: No wiki-link to filename — that creates ugly slug nodes in Graph View.
    The [[Company]] link in column 1 is the only graph connection needed.
    """
    index_path = vault_dir / "index.md"

    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    company = entity.get("company") or "Unknown"
    market = entity.get("market") or (entity.get("sector") or "—")
    valuation = entity.get("valuation") or "unknown"
    date = datetime.now().strftime("%Y-%m-%d")

    row = (
        f"| [[{company}]] | {founder} | {market} | {valuation} | {date} |"
    )

    if not index_path.exists():
        index_path.write_text(_INDEX_HEADER + row + "\n", encoding="utf-8")
        return

    content = index_path.read_text(encoding="utf-8")

    # Replace existing row for this company (handles re-research)
    pattern = rf"^\|.*\[\[{re.escape(company)}\]\].*\|.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, row, content, flags=re.MULTILINE)
    else:
        # Also check if the old format had a Profile column — update header if needed
        if "| Profile |" in content:
            content = content.replace(
                "| Company | Founder | Sector | Valuation | Researched | Profile |",
                "| Company | Founder | Sector | Valuation | Researched |",
            ).replace(
                "|---------|---------|--------|-----------|------------|---------|",
                "|---------|---------|--------|-----------|------------|",
            )
            # Remove Profile cell from any existing rows
            content = re.sub(r"(\|\s*\[\[.+?\]\]\|.+?\|\s*\d{4}-\d{2}-\d{2}\s*)\|\s*\[\[.*?\]\]\s*\|",
                             r"\1|", content)
        content = content.rstrip("\n") + "\n" + row + "\n"

    index_path.write_text(content, encoding="utf-8")


# ── log.md ────────────────────────────────────────────────────────────────────

_LOG_HEADER = """\
---
type: log
source: "见微·Timbre"
---

# Timbre Activity Log

> Append-only research record. See [[index]] for the full catalog.
> Format: `## [YYYY-MM-DD HH:MM] action | Founder · Company`

"""


def append_log(vault_dir: Path, entity: dict, action: str = "founder-research") -> None:
    """Append one entry to log.md. Never modifies existing entries."""
    log_path = vault_dir / "log.md"

    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    company = entity.get("company") or "Unknown"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = f"## [{ts}] {action} | {founder} · [[{company}]]\n\n"

    if not log_path.exists():
        log_path.write_text(_LOG_HEADER + entry, encoding="utf-8")
    else:
        existing = log_path.read_text(encoding="utf-8")
        log_path.write_text(existing + entry, encoding="utf-8")


# ── investors/ extraction ─────────────────────────────────────────────────────

# Internal navigation targets — skip these when extracting investor names
_SKIP_TARGETS = {
    "index", "log", "SCHEMA", "founders", "investors", "sectors",
    "index.md", "log.md", "SCHEMA.md",
}

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+?)(?:\|[^\[\]]+?)?\]\]")

# Canonical investor name registry: lowercase alias → display name.
# Sorted longest-first so longer aliases match before short ones (e.g.
# "andreessen horowitz" before "a16z" prevents false partial matches).
_INVESTOR_ALIASES: dict[str, str] = {
    "y combinator": "Y Combinator",
    "ycombinator": "Y Combinator",
    "y-combinator": "Y Combinator",
    "yc ": "Y Combinator",           # trailing space prevents matching "yc-backed" etc.
    "andreessen horowitz": "Andreessen Horowitz",
    "andreessen-horowitz": "Andreessen Horowitz",
    "a16z": "Andreessen Horowitz",
    "sequoia capital": "Sequoia",
    "sequoia": "Sequoia",
    "gradient ventures": "Gradient Ventures",
    "general catalyst": "General Catalyst",
    "index ventures": "Index Ventures",
    "benchmark capital": "Benchmark",
    "benchmark": "Benchmark",
    "lightspeed venture partners": "Lightspeed Venture Partners",
    "lightspeed": "Lightspeed Venture Partners",
    "tiger global management": "Tiger Global",
    "tiger global": "Tiger Global",
    "coatue management": "Coatue",
    "coatue": "Coatue",
    "khosla ventures": "Khosla Ventures",
    "bessemer venture partners": "Bessemer Venture Partners",
    "bessemer": "Bessemer Venture Partners",
    "first round capital": "First Round Capital",
    "first round": "First Round Capital",
    "insight partners": "Insight Partners",
    "spark capital": "Spark Capital",
    "founders fund": "Founders Fund",
    "greylock partners": "Greylock",
    "greylock": "Greylock",
    "matrix partners": "Matrix Partners",
    "felicis ventures": "Felicis Ventures",
    "felicis": "Felicis Ventures",
    "google ventures": "GV",
    "gv ": "GV",
    "charles river ventures": "CRV",
    "crv": "CRV",
    "new enterprise associates": "NEA",
    "nea": "NEA",
    "softbank vision fund": "SoftBank",
    "softbank": "SoftBank",
    "tencent": "Tencent",
    "paignton capital group": "Paignton Capital Group",
    "paignton capital": "Paignton Capital Group",
    "innovation endeavors": "Innovation Endeavors",
    "sv angel": "SV Angel",
    "slow ventures": "Slow Ventures",
    "social capital": "Social Capital",
    "capitalg": "CapitalG",
    "capital g": "CapitalG",
    "greenoaks capital": "Greenoaks",
    "greenoaks": "Greenoaks",
    "bain capital ventures": "Bain Capital Ventures",
    "dragoneer investment group": "Dragoneer",
    "dragoneer": "Dragoneer",
    "dst global": "DST Global",
    "temasek": "Temasek",
    "ivp": "IVP",
    "kleiner perkins": "Kleiner Perkins",
    "kpcb": "Kleiner Perkins",
    "menlo ventures": "Menlo Ventures",
    "battery ventures": "Battery Ventures",
    "redpoint ventures": "Redpoint Ventures",
    "redpoint": "Redpoint Ventures",
    "initialized capital": "Initialized Capital",
    "accel partners": "Accel",
    "accel": "Accel",
    "红杉中国": "红杉中国",
    "红杉资本": "红杉中国",
    "经纬中国": "经纬中国",
    "经纬创投": "经纬中国",
    "真格基金": "真格基金",
    "高榕资本": "高榕资本",
    "源码资本": "源码资本",
    "IDG资本": "IDG资本",
    "IDG": "IDG资本",
}

# Build sorted list (longest alias first) for greedy matching
_INVESTOR_PATTERNS: list[tuple[str, str]] = sorted(
    _INVESTOR_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
)


def _extract_investors_from_text(profile_text: str) -> list[str]:
    """
    Two-pass investor extraction — works regardless of whether the LLM wrote
    [[wiki-links]] or plain text.

    Pass 1: Extract [[InvestorName]] wiki-link format.
    Pass 2: Scan for known investor names in plain text using _INVESTOR_ALIASES.

    Scans the funding section first (lower false-positive rate), falls back to
    the whole profile if no funding section is found.

    Returns a deduped list of canonical investor names.
    """
    # Locate funding section — try Chinese headings first, then English.
    # IMPORTANT: match only `##` at start-of-line (MULTILINE) and require the
    # keyword to appear on that same heading line (no DOTALL for the header part).
    # Only the captured body uses DOTALL for multi-line content.
    _FUND_SECTION_PATTERNS = [
        # Chinese: ## 融资信息
        re.compile(r"^##\s*融资信息[^\n]*\n(.+?)(?=^##|\Z)", re.DOTALL | re.MULTILINE),
        # English ## Funding / Fundraising / Raised
        re.compile(r"^##[^\n]*[Ff]und(?:ing|rais|raise)[^\n]*\n(.+?)(?=^##|\Z)", re.DOTALL | re.MULTILINE),
        # ### sub-section
        re.compile(r"^###[^\n]*[Ff]und(?:ing|rais)[^\n]*\n(.+?)(?=^###|^##|\Z)", re.DOTALL | re.MULTILINE),
        # Broader: Financials / Investment / Investors / Seed / Series / Round
        re.compile(r"^##[^\n]*(?:Financial|Investment|Investor|Fundrais|Seed|Series|Round)[^\n]*\n(.+?)(?=^##|\Z)", re.DOTALL | re.MULTILINE),
    ]
    funding_match = None
    for pat in _FUND_SECTION_PATTERNS:
        funding_match = pat.search(profile_text)
        if funding_match:
            break
    search_text = funding_match.group(1) if funding_match else profile_text

    seen: set[str] = set()
    names: list[str] = []

    # Pass 1: wiki-links
    for m in _WIKILINK_RE.finditer(search_text):
        raw = m.group(1).strip()
        if not raw or raw in _SKIP_TARGETS or "/" in raw or "\\" in raw or len(raw) < 2:
            continue
        canonical = _INVESTOR_ALIASES.get(raw.lower(), raw)
        if canonical not in seen:
            seen.add(canonical)
            names.append(canonical)

    # Pass 2: plain-text known investors
    for alias, canonical in _INVESTOR_PATTERNS:
        if canonical in seen:
            continue
        # Whole-word match, case-insensitive; the alias may have a trailing space
        # (used to avoid false matches on short tokens like "yc")
        needle = re.escape(alias.rstrip())
        pattern = rf"(?<![A-Za-z0-9]){needle}(?![A-Za-z0-9])"
        if re.search(pattern, search_text, re.IGNORECASE):
            seen.add(canonical)
            names.append(canonical)

    return names


def upsert_investor_pages(vault_dir: Path, profile_text: str, entity: dict) -> list[str]:
    """
    For each investor found in the profile, create or update an investor entity page.

    - First time: creates investors/InvestorName.md with a portfolio list
    - Subsequent times: appends this company to the portfolio list if not already there

    Returns the list of investor names touched.
    """
    investors_dir = vault_dir / "investors"
    investors_dir.mkdir(exist_ok=True)

    investor_names = _extract_investors_from_text(profile_text)
    company = entity.get("company") or "Unknown"
    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    market = entity.get("market") or entity.get("sector") or ""
    date = datetime.now().strftime("%Y-%m-%d")
    portfolio_entry = (
        f"- [[{company}]]"
        + (f" · {founder}" if founder != "Unknown" else "")
        + (f" · {market}" if market else "")
        + f" ({date})"
    )

    touched: list[str] = []
    for name in investor_names:
        page_path = investors_dir / f"{name}.md"

        if not page_path.exists():
            content = (
                f"---\n"
                f'type: investor\n'
                f'name: "{name}"\n'
                f"created: {date}\n"
                f'tags: ["investor"]\n'
                f'source: "见微·Timbre"\n'
                f"---\n\n"
                f"# {name}\n\n"
                f"> Investor entity page — auto-maintained by 见微·Timbre.\n"
                f"> See [[index]] for full catalog · [[log]] for research history.\n\n"
                f"---\n\n"
                f"## Portfolio Companies (researched by Timbre)\n\n"
                f"{portfolio_entry}\n\n"
                f"---\n\n"
                f"## Investor Notes\n\n"
                f"暂无公开数据 — "
                f"add thesis / stage / geo focus here, or run: "
                f"`研究 {name} 的投资组合`\n"
            )
            page_path.write_text(content, encoding="utf-8")
        else:
            existing = page_path.read_text(encoding="utf-8")
            if f"[[{company}]]" not in existing:
                if "## Portfolio Companies" in existing:
                    existing = existing.replace(
                        "## Portfolio Companies (researched by Timbre)\n\n",
                        f"## Portfolio Companies (researched by Timbre)\n\n{portfolio_entry}\n",
                    )
                else:
                    existing = existing.rstrip("\n") + f"\n{portfolio_entry}\n"
                page_path.write_text(existing, encoding="utf-8")

        touched.append(name)

    return touched


# ── sectors/ pages ────────────────────────────────────────────────────────────

# Patterns to extract market/sector from profile body when entity.market is empty.
# Checked in order; first match wins.
_MARKET_PATTERNS: list[re.Pattern[str]] = [
    # Structured fields (highest confidence)
    re.compile(r"\*\*Industry\*\*[:\s]+([^\n*|]{3,60})", re.IGNORECASE),
    re.compile(r"\*\*市场[/／]赛道\*\*[:\s]+([^\n*|]{3,60})", re.IGNORECASE),
    re.compile(r"\*\*Sector\*\*[:\s]+([^\n*|]{3,60})", re.IGNORECASE),
    re.compile(r"\*\*Category\*\*[:\s]+([^\n*|]{3,60})", re.IGNORECASE),
    re.compile(r"^\*\*Industry:\*\*\s+([^\n*|]{3,60})", re.MULTILINE | re.IGNORECASE),
    # Narrative patterns
    re.compile(r"speciali[sz]es? in ([a-z][^\n.]{3,40})", re.IGNORECASE),
    re.compile(r"company.*? in the ([a-z][^\n.]{3,40}?) (?:field|space|industry|sector)", re.IGNORECASE),
    re.compile(r"leader.*? in ([a-z][^\n.]{3,40}?) (?:technology|tech|space|market)", re.IGNORECASE),
]


def _extract_market_from_profile(profile_text: str) -> str:
    """
    Extract the market/sector string from profile body text.
    Returns empty string if nothing useful found.
    """
    for pat in _MARKET_PATTERNS:
        m = pat.search(profile_text)
        if m:
            val = m.group(1).strip().strip("*").strip()
            # Reject generic / useless values
            if val and val.lower() not in ("unknown", "n/a", "—", "-", "tbd"):
                # Trim long phrases after comma/semicolon to keep it a short label
                val = re.split(r"[,;]", val)[0].strip()
                if len(val) <= 80:
                    return val
    return ""


def _sector_slug(market: str) -> str:
    """Normalize a market string into a safe filename slug."""
    slug = re.sub(r"[^\w\s\-/]", "", market).strip()
    slug = re.sub(r"[\s/]+", "-", slug)
    return slug[:60]


def upsert_sector_page(
    vault_dir: Path,
    entity: dict,
    profile_text: str = "",
) -> str | None:
    """
    Create or update a sector concept page.

    Market/sector resolution order:
      1. entity['market']
      2. entity['sector']
      3. Extracted from profile_text body (fallback)

    Returns the sector name if a page was written, None if skipped.
    """
    market = (
        entity.get("market")
        or entity.get("sector")
        or ""
    ).strip()

    if (not market or market.lower() in ("unknown", "—", "")) and profile_text:
        market = _extract_market_from_profile(profile_text)

    if not market or market.lower() in ("unknown", "—", ""):
        return None

    sectors_dir = vault_dir / "sectors"
    sectors_dir.mkdir(exist_ok=True)

    slug = _sector_slug(market)
    page_path = sectors_dir / f"{slug}.md"

    company = entity.get("company") or "Unknown"
    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    date = datetime.now().strftime("%Y-%m-%d")
    company_entry = (
        f"- [[{company}]]"
        + (f" · {founder}" if founder != "Unknown" else "")
        + f" ({date})"
    )

    if not page_path.exists():
        content = (
            f"---\n"
            f'type: sector\n'
            f'name: "{market}"\n'
            f"created: {date}\n"
            f'tags: ["sector"]\n'
            f'source: "见微·Timbre"\n'
            f"---\n\n"
            f"# {market}\n\n"
            f"> Sector concept page — auto-maintained by 见微·Timbre.\n"
            f"> See [[index]] for full catalog · [[SCHEMA]] for vault layout.\n\n"
            f"---\n\n"
            f"## Companies in This Sector (researched by Timbre)\n\n"
            f"{company_entry}\n\n"
            f"---\n\n"
            f"## Sector Overview\n\n"
            f"暂无公开数据 — run: `总结 {market} 赛道的所有创始人有哪些共同点`\n"
        )
        page_path.write_text(content, encoding="utf-8")
    else:
        existing = page_path.read_text(encoding="utf-8")
        if f"[[{company}]]" not in existing:
            if "## Companies in This Sector" in existing:
                existing = existing.replace(
                    "## Companies in This Sector (researched by Timbre)\n\n",
                    f"## Companies in This Sector (researched by Timbre)\n\n{company_entry}\n",
                )
            else:
                existing = existing.rstrip("\n") + f"\n{company_entry}\n"
            page_path.write_text(existing, encoding="utf-8")

    return market


# ── Main entry point ──────────────────────────────────────────────────────────

def update_vault(
    vault_dir: Path,
    entity: dict,
    profile_text: str,
    filename: str,
) -> dict[str, list[str] | str | None]:
    """
    Run all vault maintenance operations after a founder profile is saved.

    Order:
      1. Ensure sub-folder structure + SCHEMA.md exist
      2. Upsert index.md row
      3. Append log.md entry
      4. Upsert investor entity pages (extracted from profile text)
      5. Upsert sector concept page (entity.market or extracted from profile)

    Returns a summary dict for display purposes.
    """
    ensure_vault_structure(vault_dir)
    update_index(vault_dir, entity, filename)
    append_log(vault_dir, entity)
    investors = upsert_investor_pages(vault_dir, profile_text, entity)
    sector = upsert_sector_page(vault_dir, entity, profile_text)

    return {
        "investors_updated": investors,
        "sector_updated": sector,
    }
