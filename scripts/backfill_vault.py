#!/usr/bin/env python3
"""
scripts/backfill_vault.py
Backfill investors/ and sectors/ pages for existing founder profiles,
and fix index.md to remove ugly filename nodes.

Run from the repo root:
    python scripts/backfill_vault.py
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

# Make sure the local timbre package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from timbre.vault import (
    ensure_vault_structure,
    update_index,
    upsert_investor_pages,
    upsert_sector_page,
    _sector_slug,
)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML front-matter fields into a plain dict (values as strings)."""
    fm: dict[str, str] = {}
    m = re.match(r"^---\s*\n(.+?)\n---", text, re.DOTALL)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            key = kv[0].strip()
            val = kv[1].strip().strip('"').strip("'")
            fm[key] = val
    return fm


def guess_company_from_filename(stem: str) -> str:
    """
    Last resort: extract a readable company name from the filename stem.
    e.g. 'sam-bhagwat-mastra-2026-05-28' → 'mastra'
    """
    # Remove trailing date
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", stem)
    parts = stem.split("-")
    # Heuristic: company name is usually the last 1-2 tokens
    return parts[-1].capitalize() if parts else stem


def main() -> None:
    # Determine vault dir (same logic as cli.py)
    vault_env = os.getenv("OBSIDIAN_VAULT_PATH")
    subfolder = os.getenv("OBSIDIAN_SUBFOLDER", "Timbre")
    if vault_env:
        vault_dir = Path(vault_env) / subfolder
    else:
        vault_dir = Path.home() / ".timbre" / "profiles"

    founders_dir = vault_dir / "founders"
    if not founders_dir.exists():
        print(f"No founders/ found at {founders_dir}. Nothing to backfill.")
        return

    profiles = sorted(founders_dir.glob("*.md"))
    if not profiles:
        print("No profile files found.")
        return

    print(f"Vault: {vault_dir}")
    print(f"Found {len(profiles)} profile(s) to backfill.\n")

    ensure_vault_structure(vault_dir)

    for profile_path in profiles:
        text = profile_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        company = fm.get("company", "").strip()
        founder = fm.get("founder", "").strip()
        market = fm.get("market", "").strip() or fm.get("sector", "").strip()

        # Skip obviously bad company names (input query leaked in)
        if not company or company.startswith("研究") or len(company) > 50:
            # Try to guess from the profile title line
            title_m = re.search(r"^#\s+(.+?)(?:\n|$)", text, re.MULTILINE)
            if title_m:
                title = title_m.group(1).strip()
                # Strip subtitles after colon / em-dash / pipe
                title = re.split(r"[：:—|]", title)[0].strip()
                # Strip common filler words
                title = re.sub(r"\s*([:：,，]\s*(a|an|the|overview|analysis|profile|report)\b.*)?$", "", title, flags=re.IGNORECASE).strip()
                if len(title) >= 2 and len(title) <= 50 and not title.startswith("研究"):
                    company = title
                    print(f"  [fix] company name corrected → '{company}'")
            if not company or company.startswith("研究"):
                company = guess_company_from_filename(profile_path.stem)
                print(f"  [fix] company guessed from filename → '{company}'")

        entity = {
            "founder": founder or "Unknown",
            "company": company,
            "market": market,
        }

        print(f"Processing: {profile_path.name}")
        print(f"  entity: founder={entity['founder']!r}  company={entity['company']!r}  market={entity['market']!r}")

        # Upsert index row
        update_index(vault_dir, entity, profile_path.name)
        print(f"  index.md: updated row for [[{company}]]")

        # Upsert investor pages
        investors = upsert_investor_pages(vault_dir, text, entity)
        if investors:
            print(f"  investors/: created/updated {len(investors)} page(s): {investors}")
        else:
            print(f"  investors/: no known investors found in profile text")

        # Upsert sector page
        sector = upsert_sector_page(vault_dir, entity, text)
        if sector:
            print(f"  sectors/: created/updated → '{sector}'")
        else:
            print(f"  sectors/: no market/industry extracted")

        print()

    # Final summary
    investors_dir = vault_dir / "investors"
    sectors_dir = vault_dir / "sectors"
    inv_count = len(list(investors_dir.glob("*.md"))) if investors_dir.exists() else 0
    sec_count = len(list(sectors_dir.glob("*.md"))) if sectors_dir.exists() else 0

    print("─" * 50)
    print(f"Backfill complete.")
    print(f"  founders/  : {len(profiles)} profiles")
    print(f"  investors/ : {inv_count} pages")
    print(f"  sectors/   : {sec_count} pages")
    print(f"\nOpen Obsidian and run Cmd+Shift+G to see the updated Graph View.")


if __name__ == "__main__":
    main()
