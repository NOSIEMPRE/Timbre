# Timbre — Skill Design Document

## Trigger Conditions

This skill activates when the user inputs any of the following:
- A Chinese founder's name (e.g. 梁文锋, Yang Zhilin)
- A company name (e.g. DeepSeek, Minimax, 月之暗面)
- A product name (e.g. Kimi, Manus)
- Any combination of the above, with optional `@file` or `@url` context

**Counter-examples (do not trigger):**
- Public companies with financial reports (use Bloomberg/Wind instead)
- Non-Chinese founders
- Companies valued below ~$200M

---

## Pipeline Architecture

```
Input
  │
  ▼
Stage 1 — Entity Resolution          (ReAct, max 4 iterations)
  │  Tools: web_search, read_file
  │  Output: { founder, founder_en, company, valuation, confirmed, confidence }
  │
  ▼
Stage 2a — Research Planning         (single LLM call, no tools)
  │  Output: JSON search plan — 4 dimensions × 3-4 queries each
  │
  ▼
Stage 2b — Parallel Execution        (no LLM, direct Tavily calls)
  │  Concurrency: 5 simultaneous queries
  │  Output: resultsByDimension map
  │
  ▼
Stage 3 — Synthesis                  (ReAct, max 8 iterations)
  │  Tools: browse_url only
  │  Reads prior memory if entity was previously researched
  │  Output: structured Markdown profile
  │
  ▼
Quality Check + Memory Write
  │  Scores: word count, section coverage, URL count
  │  Writes entity to memory/store.json
  │
  ▼
Save to profiles/ or Obsidian vault
```

---

## Tool Set

| Tool | Stage | Purpose |
|------|-------|---------|
| `web_search` | 1, 2b | Tavily search, advanced depth |
| `read_file` | 1, pre-pipeline | Local files: PDF, MD, TXT, CSV, JSON |
| `browse_url` | 3 | Playwright — full article retrieval, paywalled content |

Stage 3 has access only to `browse_url`, not `web_search`. This prevents the synthesizer from re-searching and keeps stages cleanly separated.

---

## Research Dimensions

| Dimension | Chinese queries | English queries | Key sources |
|-----------|----------------|-----------------|-------------|
| Founder Profile | 访谈 世界观 创业动机 演讲 | interview podcast worldview | 即刻, 微博, podcasts |
| Team Architecture | 联合创始人 管理层 组织架构 | co-founder leadership site:linkedin.com | LinkedIn, 脉脉 |
| Product & Business | 核心产品 商业模式 业务线 | product business model revenue | 36Kr, 晚点, TechCrunch |
| Funding | 融资 估值 投资方 | funding valuation investors | IT桔子, Crunchbase, 36Kr |

---

## Output Format

Each profile opens with **核心判断** (3-5 investment-relevant conclusions), followed by narrative sections with direct quotes, specific numbers, and source citations. Saved as Markdown with YAML frontmatter compatible with Obsidian Dataview.

```yaml
---
founder: "梁文锋"
founder_en: "Liang Wenfeng"
company: "DeepSeek"
created: 2026-05-26
tags: ["founder-profile", "unicorn"]
source: "见微·Timbre"
---
```

---

## Memory System

`memory/store.json` persists entity records across sessions. Written after every successful run. Read at Stage 3 start — if prior research exists, the agent is told to update rather than restart from scratch.

---

## Quality Evaluation

`eval/quality_check.js` scores each profile post-synthesis:
- Required sections present (−20 per missing)
- Word count ≥ 800 (−15 if below)
- URL count ≥ 3 (−15 if below)
- Score 0-100, issues shown in CLI

---

## Known Limitations

1. Public information only — compensation, equity, internal conflicts are inaccessible
2. LinkedIn penetration low in China — domestic team data is often sparse
3. Funding data lags 3-6 months behind reality
4. Paywalled journalism requires user-provided cookies
5. Stage 1 accuracy drops when product name differs significantly from company name
6. Chinese social platforms (即刻, 微博) have inconsistent Tavily coverage
