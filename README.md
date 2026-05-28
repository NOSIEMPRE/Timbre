<div align="right">
  <b>中文</b> &nbsp;·&nbsp; <a href="README.en.md">EN</a>
</div>

<div align="center">
  <h1>见微 · Timbre</h1>
  <p><strong>一级市场的 Founder Intelligence System</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square" alt="Python 3.9+">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
    <img src="https://img.shields.io/badge/模型-任意_OpenAI_兼容接口-8a2be2?style=flat-square" alt="Model">
    <img src="https://img.shields.io/badge/搜索-Tavily-orange?style=flat-square" alt="Tavily">
    <img src="https://img.shields.io/badge/适用于-Claude_·_Cursor_·_Codex-1B2A4A?style=flat-square" alt="Works with">
  </p>
</div>

---

一个**越用越好用**的 Founder Intelligence System，面向一级市场投资团队。

大多数工具给你一次性的答案。Timbre 构建的是知识图谱。每一次 `founder-research` 同时写入三种节点：**创始人档案**（founders/）、**投资机构实体页**（investors/）、**赛道概念页**（sectors/）。研究 20 个项目之后，Obsidian Graph View 自动呈现任何单次搜索都看不到的东西：*Sequoia 在这个赛道押注了哪几家*、*哪些 founder 共同被同一个 LP 支持*。这种跨 session 的复利效应，才是真正的核心价值。

---

## 三层系统，协同工作

```
发现 ──────────────▶  深研 ──────────────▶  沉淀
vc-sourcing           founder-research       Obsidian wiki
主动扫描公开网络        结构化 VC 尽调档案      三种节点自动维护
Pre-Seed / Seed        8节 Markdown + 来源     founders/ · investors/ · sectors/
      ▲                                             │
      └─────────────────────────────────────────────┘
                    越用越好用
```

**vc-sourcing** — 主动发现早期项目。不需要公司名，只需一个赛道。并行扫描 HackerNews Show HN、YC W25/S25 批次、ProductHunt 新品、TechCrunch 早期报道、GitHub trending，输出按 vc_appeal 排序的项目列表。

**founder-research** — 实体识别 + 并行搜索 + 综合分析。生成完整的尽调档案，含 `[N]` 来源标注、`P0/P1/P2` 风险分级、Playwright 付费内容访问。每次保存同时更新 index.md 目录、log.md 活动记录、investor 实体页、sector 概念页。

**Stage 2.5 创始人补全** — 当 sourcing 结果中 `founder: unknown` 时，自动对 LinkedIn、Crunchbase、TechCrunch 发起定向搜索，并经过多层名称清洗验证。实测：创始人识别率从约 40% 提升至约 78%。

---

## Obsidian 知识图谱

每次 `founder-research` 写入的不是一个文件，而是整个图谱的一次更新：

```
Timbre/                        ← Obsidian vault 子目录
├── SCHEMA.md                  ← Vault 说明书（含操作指令，Claude Code 可直接读）
├── index.md                   ← 主目录，每行一个 founder，自动维护
├── log.md                     ← 活动记录，append-only
├── founders/                  ← 创始人尽调档案
│   ├── alex-mackenzie-clay-2026-01-15.md
│   └── liang-wenfeng-deepseek-2026-01-20.md
├── investors/                 ← 投资机构实体页（从 [[]] 链接自动生成）
│   ├── Sequoia.md             ← "Portfolio: Clay · DeepSeek · ..."
│   ├── a16z.md
│   └── 红杉中国.md
└── sectors/                   ← 赛道概念页（从 entity.market 自动生成）
    ├── AI-Infrastructure.md
    └── GTM-Automation.md
```

研究 20 个 founder 之后，在 Obsidian Graph View 里：
- `Sequoia` 节点连接到它投过的所有 founder
- `AI-Infrastructure` 节点聚合该赛道的全部公司
- 在 vault 里问 Claude Code：`query: 哪些 investor 在 AI Infrastructure 赛道出现了两次以上？`

> 设计参考：[Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)（2026.04）

---

## 三种使用方式

| 方式 | 配置 | 适合场景 |
|------|------|---------|
| **粘贴 `SKILL.md`** | 零安装 | Claude.ai Projects、Claude Code、Cursor、Codex——任意 system prompt |
| **本地 CLI** | `pipx install` + 2 个 API Key | 日常调研工作流、Obsidian 集成 |
| **Anthropic API Tool** | `from timbre.skill_api import TOOLS` | 嵌入自有产品 |

### 方式一：零安装（粘贴至任意 Claude 环境）

复制 [`SKILL.md`](SKILL.md) 的全部内容，粘贴至：

- **Claude.ai** → Project Instructions
- **Claude Code** → `CLAUDE.md`
- **Cursor / Codex** → system prompt 或 rules 文件

Claude 本身即成为执行引擎。无需安装依赖，不受本地模型能力限制。SKILL.md 是一份纯行为规范——触发条件、搜索策略、输出格式——任意 Claude 环境读取后直接执行。

### 方式二：本地 CLI

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
timbre config     # 交互式配置向导：选择模型提供商、填入 API Key、设置 Obsidian 路径
```

> 没有 `pipx`？→ `brew install pipx`（Mac）或 `pip install pipx`

支持所有兼容 OpenAI 接口的模型：

| 提供商 | Base URL |
|--------|----------|
| Anthropic Claude | 无需 Base URL，直接 SDK |
| DeepSeek | `https://api.deepseek.com/v1` |
| 通义千问 Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| Kimi（Moonshot AI） | `https://api.moonshot.cn/v1` |
| Ollama（本地部署） | `http://localhost:11434/v1` |

### 方式三：Anthropic API Tool

```python
import anthropic
from timbre.skill_api import TOOLS, dispatch_tool_call

client = anthropic.Anthropic()

# TOOLS 直接传入 messages.create()
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    tools=TOOLS,
    messages=[{"role": "user", "content": "帮我找最近值得关注的早期 AI infrastructure 项目"}],
)

# 将 tool_use 路由回 pipeline
for block in response.content:
    if block.type == "tool_use":
        result = await dispatch_tool_call(block.name, block.input)
```

完整 agentic loop 示例（含多轮 sourcing → 深研流程）见 [`examples/claude_api_demo.py`](examples/claude_api_demo.py)。

---

## 效果演示

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
timbre › 研究一下梁文锋

  ▸ 实体识别中       → 梁文锋 · DeepSeek  (置信度 90%)
  ▸ 制定搜索计划     计划：创始人画像 · 创始团队图谱 · 产品与商业模式 · 融资信息  共 14 条搜索
  ▸ 并行搜索中       ............
  ▸ 整理搜索结果

  质量评分  91分  字数 2840  来源 18

  更新知识图谱：投资方页面 3 个 · 赛道页面 [AI / 大模型]

  ✓  已保存至 ~/.timbre/profiles/founders/liang-wenfeng-deepseek-2026-05-28.md
```

档案片段：

```markdown
---
founder: "梁文锋"
founder_en: "Liang Wenfeng"
company: "DeepSeek / 幻方科技"
created: 2026-05-28
tags: ["founder-profile"]
---

## 核心判断

梁文锋是国内极少数同时具备量化金融背景和 LLM 研究能力的创始人……[1][3]

## 风险分级

P0  监管风险：模型能力公开展示受国内审查政策约束
P1  人才留存：核心研究员在顶级实验室报价面前的稳定性

## 融资信息

| 轮次 | 金额 | 日期 | 领投方 | 来源 |
|------|------|------|--------|------|
| 战略融资 | 未披露 | 2024 | [[红杉中国]] | [3] |

## 信息源

[1] https://mp.weixin.qq.com/s/...
[3] https://www.theinformation.com/articles/...
```

同步生成的 `investors/红杉中国.md`：

```markdown
# 红杉中国

## Portfolio Companies (researched by Timbre)

- [[DeepSeek / 幻方科技]] · 梁文锋 · AI / 大模型 (2026-05-28)
```

---

## 安装与配置

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
timbre config
```

配置保存在 `~/.timbre/.env`，不写入 repo。

| 变量 | 必填 | 说明 |
|------|------|------|
| `TAVILY_API_KEY` | ✅ | 网络搜索 — [app.tavily.com](https://app.tavily.com)（有免费额度） |
| `ANTHROPIC_API_KEY` | ✅ 二选一 | Claude 系列模型 |
| `OPENAI_API_KEY` | ✅ 二选一 | DeepSeek / Qwen / Kimi / Ollama 等 |
| `OPENAI_BASE_URL` | 配合上条 | 如 `https://api.deepseek.com/v1` |
| `MODEL` | 配合上条 | 如 `deepseek-chat`、`qwen-max`、`llama3.1:8b` |
| `OBSIDIAN_VAULT_PATH` | 可选 | 档案直接落进 Obsidian vault |
| `OBSIDIAN_SUBFOLDER` | 可选 | 默认 `Timbre` |
| `BROWSER_COOKIES_FILE` | 可选 | Netscape 格式 cookies，用于付费内容访问 |
| `LANGFUSE_SECRET_KEY` | 可选 | 可观测性追踪 — [langfuse.com](https://langfuse.com) |

**付费内容访问**（晚点、The Information、36Kr Pro 等）：用 Chrome 插件 *Get cookies.txt LOCALLY* 导出 Netscape 格式 cookies，设置 `BROWSER_COOKIES_FILE` 即可。

---

## 使用

```bash
timbre
```

直接用自然语言输入，不需要记命令。

```
# 主动发现早期项目
timbre › 帮我找最近值得关注的早期 AI 项目
timbre › 有没有 B2B SaaS 方向的新公司
timbre › sourcing healthcare pre-seed

# 深度研究创始人 / 公司
timbre › 研究一下梁文锋
timbre › DeepSeek 的创始人背景
timbre › xx 公司 @./pitch-deck.pdf @https://techcrunch.com/...

# 基于当前档案追问
timbre › 他的联创团队背景呢
timbre › 融资情况能详细说说吗

# 查询投资机构持仓
timbre › 红杉投了哪些 AI 公司
timbre › Benchmark 的 AI portfolio

# 知识图谱查询（在 Obsidian vault 里问 Claude Code）
query: 哪些 investor 在 AI Infrastructure 赛道出现了两次以上？
lint:  找出所有没有对应页面的 [[wikilink]]

# 档案与记忆
timbre › 查看我保存的档案
timbre › 退出
```

每次输入前有一次轻量意图识别，自动路由至 sourcing、research、追问、investor 查询或记忆检索，无需切换模式。

---

## 项目结构

```
Timbre/
├── SKILL.md                         行为规范文档——粘贴至任意 Claude 环境即可使用
├── examples/claude_api_demo.py      完整 Anthropic API agentic loop 示例
├── deliverable.html                 互动版 VC sourcing 演示报告
├── timbre/
│   ├── cli.py                       交互式 CLI（asyncio + Rich）
│   ├── skill_api.py                 Anthropic API Tool 定义 + 分发器
│   ├── vault.py                     Obsidian 知识图谱维护（Karpathy LLM-wiki 模式）
│   ├── observe.py                   Langfuse 追踪封装（未配置时零开销）
│   ├── pipelines/
│   │   ├── sourcing.py              vc-sourcing：多源扫描 + Stage 2.5 创始人补全
│   │   ├── founder_research.py      founder-research：四阶段 pipeline
│   │   └── investor_research.py     投资机构持仓查询
│   ├── providers/
│   │   ├── __init__.py              根据环境变量自动选择 provider
│   │   ├── anthropic_provider.py
│   │   └── openai_provider.py       任何兼容 OpenAI 接口的模型
│   ├── tools/
│   │   ├── registry.py              Tool 数据类 + 注册表
│   │   ├── web_search.py            Tavily 搜索
│   │   ├── read_file.py             PDF、MD、TXT、CSV 解析
│   │   └── browse_url.py            Playwright（付费内容访问）
│   ├── memory/
│   │   └── store.py                 SQLite FTS5 跨 session 记忆（存于 ~/.timbre/）
│   ├── eval/
│   │   └── quality_check.py         0–100 分输出质量评分
│   └── prompts/                     所有 Agent 行为定义在这里
│       ├── system.yaml              研究员人设
│       ├── entity_resolution.yaml   Stage 1 提示词
│       ├── research_plan.yaml       Stage 2a 提示词
│       └── founder_profile.yaml     Stage 3 综合分析模板
```

> 所有 Agent 行为都在 `prompts/` 里定义。修改调研方式或输出风格，只需改 YAML，不需要动业务代码。

---

## 已知局限

Timbre 只能访问**公开信息**。薪酬结构、内部管理矛盾不在覆盖范围内。股权结构和融资细节在天眼查、企查查、Crunchbase、PitchBook 等平台有付费数据——配置对应平台的 cookie 后，`browse_url` 可直接获取。

LinkedIn 在国内渗透率偏低，部分国内团队的组织信息会不完整。融资数据通常晚披露 3–6 个月。这两点是数据源本身的上限，工具层面无法解决。

产品名与公司名不一致时（如"Claude" vs"Anthropic"），Stage 1 会自动多轮搜索消歧，也可以直接附上创始人姓名或 `@链接` 加速识别。

---

## Tech Stack

Python 3.9+ · asyncio · [Tavily](https://tavily.com) · Playwright · SQLite FTS5 · [Rich](https://github.com/Textualize/rich) · [Langfuse](https://langfuse.com)（可选）

模型：任意 OpenAI 兼容接口 — Anthropic Claude · DeepSeek · Qwen · Kimi · GLM · Ollama

---

<div align="center">
  <sub>为一级市场 sourcing 和尽调而构建，与任何基金无关联。</sub>
</div>
