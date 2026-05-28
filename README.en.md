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

Early-stage sourcing is manual, repetitive, and leaky. Teams scan HN, skim TechCrunch, and page through YC batches every week — coverage stays thin, and whatever you learn doesn't carry over to the next session.

Timbre fixes two things: **coverage** and **memory**. It's a Founder Intelligence System built for primary market investors, with three layers working together: proactively discover Pre-Seed / Seed companies from public sources (no company name needed), generate structured due diligence profiles on specific founders (source-anchored facts, P0/P1/P2 risk flags), and automatically compound every research session into an Obsidian knowledge graph.

The compounding is the point. Every `founder-research` run updates investor entity pages (investors/) and sector pages (sectors/) alongside the founder profile. After 20 sessions, the Sequoia node in Obsidian Graph View connects to every founder it has backed. The AI Infrastructure node lists every company in that sector you've researched. That kind of cross-session pattern recognition is impossible with one-off searches.

---

## Three Layers, One System

```
Discover ──────────────▶  Research ──────────────▶  Compound
vc-sourcing               founder-research           Obsidian wiki
Scan public web           Structured due diligence   Three node types, auto-maintained
Pre-Seed / Seed           8-section Markdown         founders/ · investors/ · sectors/
      ▲                                                     │
      └─────────────────────────────────────────────────────┘
                      Gets better with every use
```

**vc-sourcing** takes a vertical keyword and finds the companies. Scans HackerNews Show HN, YC W25/S25 batches, ProductHunt, TechCrunch seed coverage, and GitHub trending in parallel. No company name needed.

**founder-research** takes a founder name or company name and produces an 8-section due diligence profile with per-fact source citations, P0/P1/P2 risk flags, and Playwright paywall access. Each save also updates index.md, the matching investor pages, and the sector page.

**Stage 2.5 founder enrichment** handles the `founder: unknown` cases that sourcing frequently produces. Runs a targeted search against LinkedIn, Crunchbase, and TechCrunch, then filters candidates through multiple name-validation layers. Founder identification went from around 40% to 78% in testing.

---

## Obsidian Knowledge Graph

`founder-research` writes to more than just the founder profile. Each run touches the whole graph:

```
Timbre/                        ← Obsidian vault subfolder
├── SCHEMA.md                  ← Vault schema + operations guide (readable by Claude Code)
├── index.md                   ← Master catalog, one row per founder, auto-maintained
├── log.md                     ← Activity log, append-only
├── founders/                  ← Founder due-diligence profiles
│   ├── alex-mackenzie-clay-2026-01-15.md
│   └── liang-wenfeng-deepseek-2026-01-20.md
├── investors/                 ← Investor entity pages (auto-created from [[links]])
│   ├── Sequoia.md             ← "Portfolio: Clay · DeepSeek · ..."
│   ├── a16z.md
│   └── 红杉中国.md
└── sectors/                   ← Sector concept pages (auto-created from entity.market)
    ├── AI-Infrastructure.md
    └── GTM-Automation.md
```

After 20 sessions in Obsidian Graph View:
- `Sequoia` node connects to every founder it has backed
- `AI-Infrastructure` node clusters all companies in that sector
- Open Claude Code in the vault and ask: `query: which investors appear in more than two AI Infrastructure profiles?`

> Design reference: [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (April 2026)

---

## Three Ways to Use It

| Mode | Setup | Best for |
|------|-------|---------|
| **Paste `SKILL.md`** | Zero install | Claude.ai Projects, Claude Code, Cursor, Codex |
| **Local CLI** | `pipx install` + 2 API keys | Daily research workflow, Obsidian integration |
| **Anthropic API tool** | `from timbre.skill_api import TOOLS` | Embedding in your own product |

### Mode 1: Zero Install (Paste to Any Claude Environment)

Copy the contents of [`SKILL.md`](SKILL.md) and paste into:

- **Claude.ai** → Project Instructions
- **Claude Code** → `CLAUDE.md`
- **Cursor / Codex** → system prompt or rules file

Claude becomes the execution engine. No dependencies, no local model. SKILL.md is a pure behavioral spec (trigger conditions, search strategy, output format rules) that any Claude environment reads and executes.

### Mode 2: Local CLI

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

### Mode 3: Anthropic API Tool

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

See [`examples/claude_api_demo.py`](examples/claude_api_demo.py) for a complete agentic loop with multi-turn sourcing → drill-down.

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

  ▸ 实体识别中       → Alex MacKenzie · Clay  (置信度 90%)
  ▸ 制定搜索计划     计划：创始人画像 · 创始团队图谱 · 产品与商业模式 · 融资信息  共 14 条搜索
  ▸ 并行搜索中       ............
  ▸ 整理搜索结果

  质量评分  87分  字数 2340  引用 14 处  来源 9 条

  更新知识图谱：投资方页面 2 个 · 赛道页面 [GTM Automation]

  ✓  已保存至 ~/.timbre/profiles/founders/alex-mackenzie-clay-2026-05-28.md
  💰  Cost: $0.028  (input 9,140 tok · output 2,180 tok · claude-opus-4-7)
```

Profile excerpt:

```markdown
---
founder: "Alex MacKenzie"
company: "Clay"
created: 2026-05-28
tags: ["founder-profile"]
---

## 核心判断

[[Clay]] 正在将 GTM 自动化重新定义为数据编排层……[1]

## 风险分级

P0  竞争壁垒：Salesforce/HubSpot 均可复制核心功能，护城河取决于数据网络效应建立速度
P1  创始人集中度：Alex 强个人品牌驱动社区，离开风险需评估

## 融资信息

| 轮次 | 金额 | 日期 | 领投方 | 来源 |
|------|------|------|--------|------|
| Series B | $46M | 2024 | [[Sequoia]] | [4] |
```

Auto-generated `investors/Sequoia.md`:

```markdown
# Sequoia

## Portfolio Companies (researched by Timbre)

- [[Clay]] · Alex MacKenzie · GTM Automation (2026-05-28)
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
| `TAVILY_API_KEY` | ✅ | Web search. [app.tavily.com](https://app.tavily.com) (free tier available) |
| `ANTHROPIC_API_KEY` | ✅ one of | Claude models |
| `OPENAI_API_KEY` | ✅ one of | DeepSeek / Qwen / Kimi / Ollama |
| `OPENAI_BASE_URL` | With above | e.g. `https://api.deepseek.com/v1` |
| `MODEL` | With above | e.g. `deepseek-chat`, `qwen-max`, `llama3.1:8b` |
| `OBSIDIAN_VAULT_PATH` | Optional | Save profiles directly into your vault |
| `OBSIDIAN_SUBFOLDER` | Optional | Default: `Timbre` |
| `BROWSER_COOKIES_FILE` | Optional | Netscape cookies.txt for paywalled sources |
| `LANGFUSE_SECRET_KEY` | Optional | Observability tracing. [langfuse.com](https://langfuse.com) |

**Paywalled content** (The Information, LatePost 晚点, 36Kr Pro, etc.): export cookies from your browser using the *Get cookies.txt LOCALLY* Chrome extension, save as Netscape format, and point `BROWSER_COOKIES_FILE` to the file.

---

## Usage

```bash
timbre
```

Natural language only. No commands to memorize.

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

# Knowledge graph queries (run Claude Code inside your Obsidian vault)
query: which investors appear in more than two AI Infrastructure profiles?
lint:  find all [[wikilinks]] with no corresponding page

# Memory
timbre › 查看我保存的档案
timbre › exit

# Offline quality audit (no API calls)
timbre eval
```

Each input goes through a lightweight intent classifier. Timbre routes to sourcing, research, follow-up, investor lookup, or memory. No mode switching needed.

---

## Project Structure

```
Timbre/
├── SKILL.md                         Behavioral spec — paste into any Claude environment
├── examples/claude_api_demo.py      Complete Anthropic API agentic loop demo
├── deliverable.html                 Interactive VC sourcing deliverable (demo)
├── timbre/
│   ├── cli.py                       Interactive CLI (asyncio + Rich)
│   ├── skill_api.py                 Anthropic API tool definitions + dispatcher
│   ├── vault.py                     Obsidian knowledge graph maintenance (Karpathy LLM-wiki pattern)
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
│   ├── session.py                   Session-level token usage + cost tracking (25 model pricing table)
│   ├── eval/
│   │   └── quality_check.py         Heuristic scoring (0–100) + LLM-as-Judge second-pass review
│   └── prompts/                     All agent behavior is defined here
│       ├── system.yaml              Researcher persona
│       ├── entity_resolution.yaml   Stage 1 prompts
│       ├── research_plan.yaml       Stage 2a prompts
│       ├── founder_profile.yaml     Stage 3 synthesis template
│       └── eval_judge.yaml          LLM-as-Judge reviewer prompt (triggers when score < 75)
```

> All agent behavior lives in `prompts/`. Changing how Timbre researches or writes is a YAML edit, not a code change.

---

## Known Limitations

Timbre surfaces **public information only**. Compensation, internal dynamics, and cap table details sit behind paid platforms (Tianyancha, Qichacha, Crunchbase, PitchBook). Configure the relevant cookies and `browse_url` will fetch those pages directly.

LinkedIn penetration is lower in China, making domestic team org charts sparse. Funding data typically lags reality by 3–6 months. These are data-source ceilings the tool cannot solve.

When a product name differs from the company name (e.g., "Claude" vs "Anthropic"), Stage 1 runs multiple disambiguation rounds automatically. Attaching the founder's name or an `@url` accelerates this.

---

## Tech Stack

Python 3.9+ · asyncio · [Tavily](https://tavily.com) · Playwright · SQLite FTS5 · [Rich](https://github.com/Textualize/rich) · [Langfuse](https://langfuse.com) (optional)

Model: any OpenAI-compatible endpoint. Anthropic Claude · DeepSeek · Qwen · Kimi · GLM · Ollama

---

<div align="center">
  <sub>Built for VC sourcing and due diligence. Not affiliated with any fund.</sub>
</div>
