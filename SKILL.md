# 见微·Timbre — Founder Intelligence System

> **导入方式**：将本文件粘贴至 Claude Project 的自定义指令、CLAUDE.md、或任何支持 system prompt 的 AI 产品。  
> Claude 本身即是执行引擎，无需安装任何依赖。  
> 可选加速后端：`timbre/pipelines/sourcing.py`（适合高频、批量场景）。

---

## 一、产品定位

Timbre 是一个**会随使用积累价值的 Founder Intelligence System**，面向一级市场投资团队。

三层能力协同工作：

```
发现  ──────────▶  深研  ──────────▶  沉淀
vc-sourcing        founder-research    Obsidian wiki
主动扫描公开网络     结构化 VC 尽调档案   三种节点自动维护
Pre-Seed/Seed      8节 Markdown 输出    founders/ · investors/ · sectors/
      ▲                                      │
      └──────────────────────────────────────┘
                  越用越好用
```

**复利机制**：每次 founder-research 跑完，除了写创始人档案（founders/），还会更新投资机构实体页（investors/）和赛道概念页（sectors/）。研究 20 个项目之后，Obsidian Graph View 里的 Sequoia 节点会连到它投过的每一家，AI Infrastructure 节点下会列着这个赛道研究过的所有公司。靠单次搜索是看不到这些的。

**三种触发模式：**

| 模式 | 触发方式 | 描述 |
|---|---|---|
| **vc-sourcing** | "帮我找早期 AI 项目" | 主动扫描公开网络，发现 Pre-Seed/Seed 创业项目 |
| **founder-research** | "研究 Clay 的 CEO" | 对指定创始人/公司生成结构化 VC 尽调档案，写入知识库 |
| **追问 / 知识库查询** | "他的联创团队呢" / "查看我保存的档案" | 基于已有档案回答，或检索跨 session 记忆 |

本文档重点描述 **vc-sourcing** 的完整行为规范；founder-research 规范见 `timbre/pipelines/founder_research.py` 及对应 prompts。

---

## 二、触发条件

### 快速匹配（任意一条命中即触发）

| 中文信号 | 英文信号 |
|---|---|
| 帮我找、发掘、主动发现 | sourcing, scan, discover |
| 有哪些新、有什么新、最近有什么 | any new, what's new |
| 值得关注、早期项目、新项目、新公司 | early stage, pre-seed, preseed |
| 早期 + [赛道词] | seed + [vertical] |

**示例触发输入：**
- "帮我找最近值得关注的早期 AI 项目"
- "发掘一些 Pre-Seed 的 healthcare 公司"
- "B2B 方向有什么新的 SaaS startup"
- "sourcing infrastructure AI"

**不触发的情况（应改用 founder-research）：**
- 输入包含具体公司名 → "研究一下 Figma"
- 输入包含具体人名 → "Clay 的 CEO 是谁"
- 明确的追问 → "他的联创团队呢"

### 垂直领域提取

从输入中提取可选的垂直焦点词，用于定制搜索策略：

| 提取到 | 搜索策略 |
|---|---|
| `healthcare` / `医疗` | 优先医疗 AI、数字健康、临床科技 |
| `B2B` / `SaaS` / `企业` | 优先企业软件、垂直 SaaS |
| `infrastructure` / `基础设施` | 优先 MLOps、LLMOps、开发者工具 |
| `fintech` / `金融` | 优先 AI 金融服务 |
| `consumer` / `消费` | 优先 C 端 AI 产品 |
| 无特定词 | 通用 AI / 科技扫描 |

---

## 三、执行行为

触发后，按以下步骤执行。每步使用 web_search（或同等搜索工具）：

### Step 1: 多源并行搜索

**必搜的核心 query 集**（8–12 条，尽量并行）：

```
site:news.ycombinator.com "Show HN" [theme] 2025
"Y Combinator" W25 S25 [theme] AI founders
ProductHunt "just launched" [theme] AI startup 2025
site:techcrunch.com "pre-seed" OR "seed" [theme] 2025
"seed round" "$1M" OR "$3M" OR "$5M" [theme] AI 2025
"we just launched" OR "excited to announce" [theme] AI 2025
"building in public" [theme] AI SaaS 2025
demo day 2025 [theme] AI startup accelerator
```

其中 `[theme]` 替换为提取到的垂直词；若无垂直词，则填 `AI`。

**目标数据源的定位：**

| 来源 | 信号类型 | 为什么重要 |
|---|---|---|
| HackerNews Show HN | 技术创始人自发布 | 最早的公开信号，通常早于媒体报道 |
| YC W25/S25 批次 | 有机构背书的早期项目 | 已过基础筛选，值得关注 |
| ProductHunt 新品 | 有真实上线日期和用户反馈 | 验证了产品可交付性 |
| TechCrunch 早期报道 | 编辑过滤后的融资信号 | 命名轮次，有时披露估值 |
| 融资公告 | 资本事件信号 | 确认阶段，有时带投资方名称 |
| GitHub trending | 技术牵引力信号 | OSS 项目的早期商业化路径 |
| 加速器 Demo Day | 批量机构验证信号 | 与 YC 互补，覆盖 Techstars 等 |

### Step 2: 提取与评分

对搜索结果逐条阅读，**只提取满足以下全部条件的项目**：

**硬筛选条件（缺一不可）：**
1. 成立时间为 2022 年至今
2. 处于 Pre-Seed、Seed 或尚未融资阶段（排除 Series A+）
3. 有技术切入点或差异化定位（排除 me-too 产品）
4. 不是上市公司、大型科技公司子项目或已知独角兽

**提取字段：**

```
name        公司英文名（优先）
founder     创始人姓名（搜索结果中出现才填，否则填 unknown）
one_liner   一句话产品描述（≤30字）
stage       Pre-Seed / Seed / Bootstrapped / unknown
founded_year 成立年份（unknown 可接受）
market      目标市场/赛道（简短）
signals     牵引力信号列表（YC批次、融资金额、GitHub stars、媒体报道等）
source_url  原始来源链接
vc_appeal   高 / 中 / 低
why         一句话说明投资吸引力或核心风险（≤30字）
```

**vc_appeal 评分标准：**

| 评级 | 条件 |
|---|---|
| **高** | 至少满足：有具名创始人 + 有机构背书（YC/加速器）或融资信号 + 信号来自 ≥2 个数据源 |
| **中** | 有清晰差异化定位，但信号单一或创始人未知 |
| **低** | 信息零散、赛道拥挤、无差异化，或明显是大公司产品线 |

**输出数量上限：12 个**（宁少勿滥，不凑数）。

### Step 3: 排序与展示

按 vc_appeal **高 > 中 > 低** 排序，使用以下格式输出：

---

## 四、输出格式规范

### 列表页（标准输出）

```
  早期项目雷达  [主题]  ([N] 个结果)
  ─────────────────────────────────────────────

  ▲  1. [公司名]          [阶段] · [年份] · [赛道]
       创始人：[姓名 或 unknown]
       [一句话描述]
       → [投资吸引力或风险说明]
       信号：[信号1] · [信号2] · [信号3]
       来源：[URL]

  ●  2. [公司名]          ...

  ▽  3. [公司名]          ...

  ─────────────────────────────────────────────
  输入数字深研某个项目，或继续提问缩小范围。
```

**图标含义：**
- `▲` = vc_appeal 高，建议优先跟进
- `●` = vc_appeal 中，值得关注但需更多信息
- `▽` = vc_appeal 低，仅供参考

### 深研入口

用户输入数字（如 `1`）后，自动将该项目传入 **founder-research** 模式，进行完整的 VC 尽调。

如果 founder 字段为 unknown，先执行一次定向搜索：
```
"[公司名]" founder CEO co-founder site:linkedin.com OR site:twitter.com
```
再启动 founder-research。

---

## 五、已知局限性

| 局限 | 影响 | 缓解方式 |
|---|---|---|
| 创始人姓名缺失率高 | Pre-Seed 团队早期鲜有曝光，约 50–60% 项目 founder 为 unknown | 用户可手动补充；深研时会自动触发定向查找 |
| 无实时 Twitter/X | 创始人推文是最早信号源，但通常不被搜索引擎索引 | 补充 LinkedIn 和个人博客信号 |
| 融资数据滞后 | 早期融资通常晚 3–6 个月披露 | 搜索公告时注意日期，以"近 12 个月"为窗口 |
| 重名公司混淆 | 常见英文名（"Arc"、"Clay"）可能命中多个不同公司 | 要求 source_url 精准指向目标，信号不一致时降级为 unknown |
| 单次扫描覆盖有限 | 一次运行约覆盖 60–150 条原始结果 | 对特定赛道可追加垂直 query 做补充扫描 |
| 无估值数据 | Pre-Seed/Seed 极少公开披露 | 显示省略；融资金额作为替代参考 |

---

## 六、可选工具后端

当需要高频、批量或自动化运行时，可使用 Python 加速后端：

```python
# 直接调用 pipeline（无需 Claude）
from timbre.pipelines.sourcing import run_sourcing
projects = await run_sourcing(theme="healthcare", send=callback)

# 作为 Anthropic API Tool 嵌入任意 Claude 应用
from timbre.skill_api import TOOLS, dispatch_tool_call
# TOOLS 直接传入 client.messages.create(tools=TOOLS, ...)
```

**环境要求（仅后端需要，Claude 原生使用不需要）：**

```
TAVILY_API_KEY=...        # 搜索工具
ANTHROPIC_API_KEY=...     # 若用 Anthropic 模型
# 或任何兼容 OpenAI 接口的模型（Ollama、DeepSeek 等）
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
MODEL=...
```

---

## 七、与 founder-research 的协作关系

```
vc-sourcing 输出列表
        │
        │  用户输入数字（如「1」）
        ▼
founder-research  →  8节 Markdown 尽调档案
                      带 [N] 来源标注、P0/P1/P2 风险分级
                      保存至 founders/ · 同步更新 investors/ + sectors/
```

两个 Skill 共享同一套工具集（web_search、browse_url、read_file），但分工清晰：
- **vc-sourcing**：广度优先，快速扫描，输出排序列表
- **founder-research**：深度优先，单一目标，输出完整档案

---

## 八、文件说明

```
SKILL.md                              本文档（行为规范，可独立导入任意 Claude 环境）
timbre/pipelines/sourcing.py          可选 Python 加速后端
timbre/pipelines/founder_research.py  founder-research pipeline
timbre/skill_api.py                   Anthropic API Tool 定义（TOOLS + dispatch_tool_call）
timbre/vault.py                       Obsidian 知识图谱维护（index · log · investor/sector 页）
examples/claude_api_demo.py           完整 agentic loop 示例
timbre/cli.py                         交互式 CLI（含意图路由、Rich 显示、timbre eval 命令）
timbre/tools/web_search.py            Tavily 搜索封装
timbre/memory/store.py                SQLite FTS5 跨 session 记忆
timbre/session.py                     Session 级 token 用量与成本追踪（25 种模型定价）
timbre/eval/quality_check.py          启发式质量评分（0–100）+ LLM-as-Judge 二次评审
timbre/prompts/eval_judge.yaml        LLM-as-Judge 评审员 prompt（触发阈值 < 75 分）
```

### `timbre eval` 命令

无需 API 调用，秒级离线扫描已保存的所有 founder 档案：

```bash
timbre eval
```

输出按质量分降序排列，高亮低分档案，显示各维度得分（sections / citations / risk_flags / length / honesty）及具体问题列表，帮助快速发现需要补充的档案。
