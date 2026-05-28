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
    ├── investors/      ← Investor entity pages (auto-created from [[]] links)
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
├── investors/       ← Investor entity pages (auto-created from [[links]])
└── sectors/         ← Sector / theme concept pages (auto-created)
```

## Node Types

| Type | Location | Created by |
|------|----------|-----------|
| Founder profile | `founders/` | `founder-research` |
| Investor entity | `investors/` | Auto-extracted from `[[InvestorName]]` in profiles |
| Sector concept | `sectors/` | Auto-created from founder's market field |

## Cross-linking Conventions

- Investor names in profiles → written as `[[Sequoia]]`, `[[红杉中国]]`, `[[a16z]]`
- Corresponding pages → `investors/Sequoia.md`, etc.
- Sector pages → `sectors/AI-Infrastructure.md`
- All pages link back to `[[index]]` and `[[log]]`

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

| Company | Founder | Sector | Valuation | Researched | Profile |
|---------|---------|--------|-----------|------------|---------|
"""


def update_index(vault_dir: Path, entity: dict, filename: str) -> None:
    """
    Upsert one catalog row in index.md.
    If the company already has a row, replace it (handles re-research + updates).
    """
    index_path = vault_dir / "index.md"

    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    company = entity.get("company") or "Unknown"
    market = entity.get("market") or "—"
    valuation = entity.get("valuation") or "unknown"
    date = datetime.now().strftime("%Y-%m-%d")
    rel_path = f"founders/{filename}"

    row = (
        f"| [[{company}]] | {founder} | {market} | {valuation} "
        f"| {date} | [[{filename.replace('.md', '')}\\|→]] |"
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


# ── investors/ pages ──────────────────────────────────────────────────────────

# Targets to skip — these are internal navigation links, not investor names
_SKIP_TARGETS = {
    "index", "log", "SCHEMA", "founders", "investors", "sectors",
    "index.md", "log.md", "SCHEMA.md",
}

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+?)(?:\|[^\[\]]+?)?\]\]")


def _extract_investor_links(profile_text: str) -> list[str]:
    """
    Extract [[InvestorName]] wiki-links from the funding section of a profile.
    Falls back to scanning the whole profile if no funding section found.
    Returns a deduped list of investor names.
    """
    # Look for the funding section first — reduces false positives
    funding_match = re.search(
        r"##\s*融资信息(.+?)(?=^##|\Z)", profile_text, re.DOTALL | re.MULTILINE
    )
    search_text = funding_match.group(1) if funding_match else profile_text

    seen: set[str] = set()
    names: list[str] = []
    for m in _WIKILINK_RE.finditer(search_text):
        name = m.group(1).strip()
        if name and name not in _SKIP_TARGETS and name not in seen:
            # Basic sanity: investor names don't contain slashes or look like file paths
            if "/" not in name and "\\" not in name and len(name) >= 2:
                seen.add(name)
                names.append(name)
    return names


def upsert_investor_pages(vault_dir: Path, profile_text: str, entity: dict) -> list[str]:
    """
    For each [[InvestorName]] in the profile, create or update an investor entity page.

    - First time: creates investors/InvestorName.md with a portfolio list
    - Subsequent times: appends this company to the portfolio list (if not already there)

    Returns the list of investor names touched.
    """
    investors_dir = vault_dir / "investors"
    investors_dir.mkdir(exist_ok=True)

    investor_names = _extract_investor_links(profile_text)
    company = entity.get("company") or "Unknown"
    founder = entity.get("founder") or entity.get("founder_en") or "Unknown"
    market = entity.get("market") or ""
    date = datetime.now().strftime("%Y-%m-%d")
    portfolio_entry = (
        f"- [[{company}]]"
        + (f" · {founder}" if founder != "Unknown" else "")
        + (f" · {market}" if market else "")
        + f" ({date})"
    )

    touched: list[str] = []
    for name in investor_names:
        # Use the investor name directly as the filename (Obsidian convention)
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
                    # Insert new entry right after the section header
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

def _sector_slug(market: str) -> str:
    """Normalize a market string into a safe filename slug."""
    slug = re.sub(r"[^\w\s\-/]", "", market).strip()
    slug = re.sub(r"[\s/]+", "-", slug)
    return slug[:60]


def upsert_sector_page(vault_dir: Path, entity: dict) -> str | None:
    """
    Create or update a sector concept page based on entity['market'].
    Returns the sector name if a page was written, None if skipped.
    """
    market = (entity.get("market") or "").strip()
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
      4. Upsert investor entity pages (extracted from [[links]] in profile)
      5. Upsert sector concept page (from entity.market)

    Returns a summary dict for display purposes.
    """
    ensure_vault_structure(vault_dir)
    update_index(vault_dir, entity, filename)
    append_log(vault_dir, entity)
    investors = upsert_investor_pages(vault_dir, profile_text, entity)
    sector = upsert_sector_page(vault_dir, entity)

    return {
        "investors_updated": investors,
        "sector_updated": sector,
    }
