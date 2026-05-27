<div align="right">
  <a href="README.md">中文</a> &nbsp;·&nbsp; <b>EN</b>
</div>

<div align="center">
  <h1>见微 · Timbre</h1>
  <p><strong>Founder Intelligence System for Primary Market Investors</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square" alt="Python 3.9+">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
    <img src="https://img.shields.io/badge/model-any_OpenAI_compatible-8a2be2?style=flat-square" alt="Model">
    <img src="https://img.shields.io/badge/search-Tavily-orange?style=flat-square" alt="Tavily">
    <img src="https://img.shields.io/badge/works_with-Claude_·_Cursor_·_Codex-1B2A4A?style=flat-square" alt="Works with">
  </p>
</div>

---

A compound intelligence system for VC sourcing and founder research — **the more you use it, the more valuable it gets.**

Most tools give you a one-shot answer. Timbre builds a knowledge graph. Every `founder-research` session writes a Markdown node with `[[Benchmark]]` and `[[a16z]]` wiki links. After 20 profiles, Obsidian Graph View surfaces patterns no single search can find: *who is betting on this sector*, *which founders share the same LP*. That cross-session compounding is the core value — not any individual query.

---

## Three Layers, One System

```
Discover ──────────────▶  Research ──────────────▶  Compound
vc-sourcing               founder-research           Obsidian wiki
Scan public web           Structured due diligence   [[investor]] graph
Pre-Seed / Seed           8-section Markdown         Graph View clustering
      ▲                                                     │
      └─────────────────────────────────────────────────────┘
                      Gets better with every use
```

**vc-sourcing** — proactive startup discovery across HackerNews Show HN, YC W25/S25 batches, ProductHunt launches, TechCrunch seed coverage, and GitHub trending. No company name needed — just a vertical.

**founder-research** — entity resolution + parallel search + synthesis. Outputs a full profile with `[N]` source citations, `P0/P1/P2` risk tiers, and paywall access via Playwright. Saves to `~/.timbre/profiles/` or directly into your Obsidian vault.

**Stage 2.5 founder enrichment** — when a sourcing result has `founder: unknown`, Timbre auto-runs a targeted search against LinkedIn, Crunchbase, and TechCrunch with multi-layer name validation. In testing: founder identification improved from ~40% to ~78%.

---

## Three Ways to Use It

| Mode | Setup | Best for |
|------|-------|---------|
| **Paste `SKILL.md`** | Zero install | Claude.ai Projects, Claude Code, Cursor, Codex — any system prompt |
| **Local CLI** | `pipx install` + 2 API keys | Daily research workflow, Obsidian integration |
| **Anthropic API tool** | `from timbre.skill_api import TOOLS` | Embedding in your own product |

### Mode 1 — Zero Install (Paste to Any Claude Environment)

Copy the contents of [`SKILL.md`](SKILL.md) and paste into:

- **Claude.ai** → Project Instructions
- **Claude Code** → `CLAUDE.md`
- **Cursor / Codex** → system prompt or rules file

Claude becomes the execution engine. No dependencies, no local model. The SKILL.md is a pure behavioral spec — trigger conditions, step-by-step search strategy, output format rules — that any Claude environment reads and executes.

### Mode 2 — Local CLI

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
timbre config     # interactive setup: model provider, API keys, Obsidian path
```

> No `pipx`? → `brew install pipx` on Mac · `pip install pipx` anywhere

Supports any OpenAI-compatible endpoint out of the box:

| Provider | Base URL |
|----------|----------|
| Anthropic Claude | (direct SDK, no base URL needed) |
| DeepSeek | `https://api.deepseek.com/v1` |
| 通义千问 Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| Kimi (Moonshot) | `https://api.moonshot.cn/v1` |
| Ollama (local) | `http://localhost:11434/v1` |

### Mode 3 — Anthropic API Tool

```python
import anthropic
from timbre.skill_api import TOOLS, dispatch_tool_call

client = anthropic.Anthropic()

# TOOLS drops straight into messages.create()
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    tools=TOOLS,
    messages=[{"role": "user", "content": "帮我找最近值得关注的早期 AI infrastructure 项目"}],
)

# Route tool calls back to the pipeline
for block in response.content:
    if block.type == "tool_use":
        result = await dispatch_tool_call(block.name, block.input)
```

See [`example_claude_api.py`](example_claude_api.py) for a complete agentic loop with multi-turn sourcing → drill-down.

---

## Demo

### vc-sourcing

```
timbre › 帮我找最近值得关注的早期 AI infrastructure 项目

  早期项目雷达  AI Infrastructure  (6 个结果)
  ─────────────────────────────────────────────────────────

  ▲  1. Miyagi Labs          Seed · 2024 · EdTech / AI 辅导
       创始人：Tyrone Davis III, Guang Cui
       为考试备考提供人工智能辅导老师
       → 双创始人可溯源，YC W25，高频刚需赛道，东南亚/印度市场
       信号：YC W25 · 国际化创始团队 · K12 刚需

  ▲  2. MiroLumari           Seed · 2024 · No-code 企业工具
       创始人：Eshani Mehta
       提供无需编码的内部应用创建平台
       → AI-native Retool，企业买方意愿已由市场验证
       信号：YC W25 · B2B SaaS · 企业软件白地

  ●  3. Emergent             Seed · 2024 · AI 代码生成
       创始人：unknown  ← Stage 2.5 触发定向搜索…
       生成并部署生产应用的自主编码代理
       信号：YC W25 · TechCrunch 报道 · GitHub trending

  ─────────────────────────────────────────────────────────
  输入数字深研某个项目，或继续提问缩小范围。

timbre › 1
  → 开始研究 Tyrone Davis III Miyagi Labs …
```

### founder-research

```
timbre › 研究 Clay 的 CEO

  ● Stage 1  实体识别…
  ● Stage 2a 制定调研计划…   (12 queries / 4 dimensions)
  ● Stage 2b 并行搜索…       (12 threads)
  ● Stage 3  综合分析…

  ✓  档案已保存  →  ~/.timbre/profiles/clay-alex-mackenzie.md
     质量评分：87 / 100
```

Profile excerpt:

```markdown
---
founder: "Alex MacKenzie"
company: "Clay"
stage: "Series B"
---

## 核心判断

Clay 正在将 GTM 自动化重新定义为数据编排层……[1]

## 风险分级

P0  竞争壁垒：Salesforce/HubSpot 均可复制核心功能，护城河取决于数据网络效应建立速度
P1  创始人集中度：Alex 强个人品牌驱动社区，离开风险需评估
```

---

## Installation & Configuration

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
timbre config
```

Config is stored at `~/.timbre/.env` and never touches the repo.

| Variable | Required | Description |
|----------|----------|-------------|
| `TAVILY_API_KEY` | ✅ | Web search — [app.tavily.com](https://app.tavily.com) (free tier available) |
| `ANTHROPIC_API_KEY` | ✅ one of | Claude models |
| `OPENAI_API_KEY` | ✅ one of | DeepSeek / Qwen / Kimi / Ollama |
| `OPENAI_BASE_URL` | With above | e.g. `https://api.deepseek.com/v1` |
| `MODEL` | With above | e.g. `deepseek-chat`, `qwen-max`, `llama3.1:8b` |
| `OBSIDIAN_VAULT_PATH` | Optional | Save profiles directly into your vault |
| `OBSIDIAN_SUBFOLDER` | Optional | Default: `Timbre` |
| `BROWSER_COOKIES_FILE` | Optional | Netscape cookies.txt for paywalled sources |
| `LANGFUSE_SECRET_KEY` | Optional | Observability — [langfuse.com](https://langfuse.com) |

**Paywalled content** (The Information, LatePost 晚点, 36Kr Pro, etc.): export cookies from your browser using the *Get cookies.txt LOCALLY* Chrome extension, save as Netscape format, and point `BROWSER_COOKIES_FILE` to the file.

---

## Usage

```bash
timbre
```

Natural language only — no commands to memorize.

```
# Proactive sourcing
timbre › 帮我找最近值得关注的早期 AI 项目
timbre › 有没有 B2B SaaS 方向的新公司
timbre › sourcing healthcare pre-seed

# Founder / company research
timbre › 研究一下梁文锋
timbre › DeepSeek 的创始人背景
timbre › Clay 的 CEO @./pitch-deck.pdf @https://techcrunch.com/...

# Follow-up on current profile
timbre › 他的联创团队背景呢
timbre › 融资情况能详细说说吗

# Investor portfolio
timbre › 红杉投了哪些 AI 公司
timbre › Benchmark 的 AI portfolio

# Memory
timbre › 查看我保存的档案
timbre › exit
```

Each input goes through a lightweight intent classifier. Timbre routes to sourcing, research, follow-up, investor lookup, or memory — no mode switching needed.

---

## Project Structure

```
Timbre/
├── SKILL.md                         Behavioral spec — paste into any Claude environment
├── example_claude_api.py            Complete Anthropic API agentic loop demo
├── deliverable.html                 Interactive VC sourcing deliverable (demo)
├── timbre/
│   ├── cli.py                       Interactive CLI (asyncio + Rich)
│   ├── skill_api.py                 Anthropic API tool definitions + dispatcher
│   ├── observe.py                   Langfuse tracing (no-op if unconfigured)
│   ├── pipelines/
│   │   ├── sourcing.py              vc-sourcing: multi-source scan + Stage 2.5 enrichment
│   │   ├── founder_research.py      founder-research: 4-stage pipeline
│   │   └── investor_research.py     investor portfolio lookup
│   ├── providers/
│   │   ├── __init__.py              Auto-selects provider from env
│   │   ├── anthropic_provider.py
│   │   └── openai_provider.py       Any OpenAI-compatible endpoint
│   ├── tools/
│   │   ├── registry.py              Tool dataclass + registries
│   │   ├── web_search.py            Tavily search
│   │   ├── read_file.py             PDF, MD, TXT, CSV
│   │   └── browse_url.py            Playwright (paywall access)
│   ├── memory/
│   │   └── store.py                 SQLite FTS5 — stored in ~/.timbre/
│   ├── eval/
│   │   └── quality_check.py         0–100 output quality scoring
│   └── prompts/                     All agent behavior is defined here
│       ├── system.yaml              Researcher persona
│       ├── entity_resolution.yaml   Stage 1 prompts
│       ├── research_plan.yaml       Stage 2a prompts
│       └── founder_profile.yaml     Stage 3 synthesis template
```

> All agent behavior lives in `prompts/`. Changing how Timbre researches or writes requires no code changes — only YAML edits.

---

## Known Limitations

Timbre surfaces **public information only**. Compensation, internal dynamics, and cap table details sit behind paid platforms (Tianyancha, Qichacha, Crunchbase, PitchBook) — configure the relevant cookies and `browse_url` will fetch those pages directly.

LinkedIn penetration is lower in China, making domestic team org charts sparse. Funding data typically lags reality by 3–6 months. These are data-source ceilings the tool cannot solve.

When a product name differs from the company name (e.g., "Claude" vs "Anthropic"), Stage 1 runs multiple disambiguation rounds automatically. Attaching the founder's name or an `@url` accelerates this.

---

## Tech Stack

Python 3.9+ · asyncio · [Tavily](https://tavily.com) · Playwright · SQLite FTS5 · [Rich](https://github.com/Textualize/rich) · [Langfuse](https://langfuse.com) (optional)

Model: any OpenAI-compatible endpoint — Anthropic Claude · DeepSeek · Qwen · Kimi · GLM · Ollama

---

<div align="center">
  <sub>Built for VC sourcing and due diligence. Not affiliated with any fund.</sub>
</div>
