<div align="right">
  <a href="README.md">中文</a> &nbsp;·&nbsp; <b>EN</b>
</div>

# 见微 · Timbre

Primary market research has never lacked data. What it lacks is the ability to turn scattered fragments into a coherent picture of a person.

A founder's worldview surfaces in a podcast from three years ago. Organizational shifts show up quietly in LinkedIn title updates. Strategic priorities bleed into the phrasing of job postings. All of this is public — and none of it is in any database.

Timbre is a founder intelligence agent for the Chinese startup ecosystem. Give it a name, a company, or a product — it confirms who you're asking about, researches them across four dimensions, and compiles a structured profile with actual judgments, not just data points.

---

## How It Works

Four stages, not one big loop.

```
Stage 1   Entity Resolution    ReAct loop      Confirms founder + company from any input
Stage 2a  Research Plan        Single LLM      Generates ~12 targeted queries across 4 dimensions
Stage 2b  Parallel Search      Promise.all     All queries run simultaneously via Tavily
Stage 3   Synthesis            ReAct + tools   Writes the profile; fetches full articles when needed
```

Stage 3 can call `browse_url` mid-synthesis to retrieve full articles from paywalled sources — if you have a subscription and configure your cookies.

---

## Capabilities

**Inputs**
- Web search across Chinese and English sources
- Local files via `@path` — pitch decks, meeting notes, PDFs, markdown
- Specific URLs via `@https://...` — including paywalled articles
- Cross-session memory — prior research on the same founder is surfaced automatically

**Output**
- Profile sections: key judgments · founder portrait · team · product · funding · sources
- Saved as Markdown with YAML frontmatter (Obsidian Dataview-compatible)
- Wiki links auto-added for graph view
- Profiles go to `profiles/` or directly into your Obsidian vault

---

## Setup

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
playwright install chromium
timbre config
```

That's it. `timbre config` walks you through the required API keys interactively.

> Don't have pipx? `brew install pipx` on Mac, or `pip install pipx` on any platform.

Timbre supports any OpenAI-compatible endpoint — DeepSeek, Qwen, GLM, Kimi, Ollama, and others.

**Paywalled content** — export your browser cookies to Netscape format (Chrome extension: *Get cookies.txt LOCALLY*) and set `BROWSER_COOKIES_FILE` in your config.

**Obsidian** — set `OBSIDIAN_VAULT_PATH` to save profiles directly into your vault.

**Observability** — set `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY` to enable Langfuse tracing. Optional.

---

## Usage

```bash
timbre
```

Just talk to it. No commands to memorize.

```
timbre › tell me about the founder of DeepSeek
timbre › what's his team background?         ← follow-up on current research
timbre › more detail on the funding rounds   ← keep asking
timbre › now research Minimax, use this @./meeting-notes.md
timbre › 月之暗面 @https://www.theinformation.com/articles/...
timbre › show me my saved profiles
timbre › exit
```

Each input goes through a lightweight intent classifier. Timbre figures out whether you're starting new research, asking a follow-up about the current profile, or doing something else — and routes accordingly. `@path` and `@url` can be appended to any query to inject local files or specific articles before synthesis.

---

## Project Structure

```
Timbre/
├── cli.py                          Interactive CLI (asyncio + Rich)
├── observe.py                      Langfuse tracing wrapper (no-op if unconfigured)
├── pipelines/
│   └── founder_research.py         Four-stage pipeline
├── providers/
│   ├── anthropic_provider.py
│   ├── openai_provider.py          Any OpenAI-compatible endpoint
│   └── __init__.py                 Auto-selects provider from env
├── tools/
│   ├── registry.py                 Tool dataclass + RESEARCH/SYNTHESIS registries
│   ├── web_search.py               Tavily
│   ├── read_file.py                PDF, MD, TXT, CSV
│   └── browse_url.py               Playwright (paywalled content)
├── memory/
│   └── store.py                    SQLite + FTS5 cross-session memory
├── prompts/
│   ├── system.yaml                 Researcher persona
│   ├── entity_resolution.yaml      Stage 1
│   ├── research_plan.yaml          Stage 2a
│   └── founder_profile.yaml        Stage 3 synthesis
├── eval/
│   └── quality_check.py
└── profiles/                       Saved profiles (gitignored)
```

All agent behavior is defined in `prompts/`. Changing how the agent researches or writes requires no code changes.

---

## Known Limitations

Timbre only surfaces public information. Compensation, true equity splits, and internal dynamics are outside its reach.

LinkedIn penetration is lower in China — organizational details for domestic teams are often sparse. Funding data typically lags reality by three to six months.

Paywalled articles require a cookies file. Without one, the agent works from search snippets only.

When a product name differs from the company name, including the founder's name improves Stage 1 accuracy.

---

## Tech Stack

Python · asyncio · Anthropic Claude · Tavily · Playwright · SQLite · Rich · Langfuse (optional)
