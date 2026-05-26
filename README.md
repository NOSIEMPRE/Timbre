<div align="right">
  <b>中文</b> &nbsp;·&nbsp; <a href="README.en.md">EN</a>
</div>

# 见微 · Timbre

一级市场的信息获取从来不缺数据，缺的是把碎片拼成完整图像的能力。

一个 founder 的世界观藏在三年前的播客访谈里，组织架构的变化写在 LinkedIn 的职位更新里，战略重心的转移隐约体现在招聘 JD 的措辞里。这些信息都是公开的，但没有人有时间把它们系统地找齐、读懂、拼在一起。

Timbre 做的就是这件事。给它一个输入——创始人姓名、公司名或核心产品名——它会自己找到对的人，从四个维度展开全球调研，输出一份有判断力的情报档案，而不只是数据的堆砌。

---

## 工作原理

四个阶段，不是一个大循环。

```
Stage 1   实体识别    ReAct loop      从任意输入确认创始人和公司
Stage 2a  制定计划    单次 LLM 调用   生成约 12 条精准搜索 query，覆盖 4 个维度
Stage 2b  并行搜索    Promise.all     所有 query 同时运行，直接调用 Tavily
Stage 3   综合分析    ReAct + 工具    撰写档案；必要时主动获取完整文章
```

Stage 3 可以在综合分析过程中调用 `browse_url`，获取付费媒体的完整文章——前提是你有订阅并配置了 cookie。

---

## 能力

**输入**
- 中英文网络搜索（Tavily）
- 本地文件 `@路径` — pitch deck、会议笔记、PDF、Markdown
- 指定 URL `@https://...` — 包括付费墙后的文章
- 跨 session 记忆 — 之前调研过的 founder 会自动被识别

**输出**
- 档案结构：核心判断 · Founder 画像 · 创始团队 · 产品与商业 · 融资信息 · 信息源
- 带 YAML frontmatter 的 Markdown（兼容 Obsidian Dataview 插件）
- 自动添加 wiki 链接，支持 Obsidian graph view
- 存入 `profiles/` 或直接落在 Obsidian vault

---

## 安装

```bash
pipx install git+https://github.com/NOSIEMPRE/Timbre.git
playwright install chromium
timbre config
```

三行搞定。`timbre config` 会引导你交互式填入 API Key，不需要手动编辑配置文件。

> 没有 pipx？Mac 上运行 `brew install pipx`，其他平台运行 `pip install pipx`。

支持所有兼容 OpenAI 接口的模型——DeepSeek、通义千问、智谱 GLM、Kimi、Ollama 本地部署等。

**访问付费内容** — 用 Chrome 扩展（*Get cookies.txt LOCALLY*）导出 cookies.txt，在 config 里配置路径。

**Obsidian 集成** — 设置 `OBSIDIAN_VAULT_PATH`，档案直接落进你的 vault。

**可观测性** — 设置 `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY` 开启链路追踪，不配置则零影响。

---

## 使用

```bash
timbre
```

启动后直接用自然语言输入，不需要记命令。

```
timbre › 帮我研究一下 xxx 公司的创始人
timbre › xx 公司的创始人背景是什么
timbre › 他的联创团队呢              ← 追问，基于刚才的研究回答
timbre › 融资情况能详细说说吗        ← 继续追问
timbre › 再研究一下 xxx，参考这个 @./meeting-notes.md
timbre › xx 公司 @https://www.theinformation.com/articles/...
timbre › 查看我保存的档案
timbre › 退出
```

每次查询前有一次轻量意图识别，Timbre 会判断你是在发起新研究、追问当前档案，还是想做其他操作。`@路径` 和 `@链接` 可以在任意查询中附加，会在综合分析前注入。

---

## 项目结构

```
Timbre/
├── cli.py                          交互式 CLI（asyncio + Rich）
├── observe.py                      Langfuse 追踪封装（未配置时零开销）
├── pipelines/
│   └── founder_research.py         四阶段 pipeline
├── providers/
│   ├── anthropic_provider.py
│   ├── openai_provider.py          任何兼容 OpenAI 接口的模型
│   └── __init__.py                 根据环境变量自动选择 provider
├── tools/
│   ├── registry.py                 Tool 数据类 + RESEARCH/SYNTHESIS 注册表
│   ├── web_search.py               Tavily 搜索
│   ├── read_file.py                PDF、MD、TXT、CSV 解析
│   └── browse_url.py               Playwright（付费内容访问）
├── memory/
│   └── store.py                    SQLite + FTS5 跨 session 实体记忆
├── prompts/
│   ├── system.yaml                 研究员人设
│   ├── entity_resolution.yaml      Stage 1
│   ├── research_plan.yaml          Stage 2a
│   └── founder_profile.yaml        Stage 3 综合分析模板
├── eval/
│   └── quality_check.py
└── profiles/                       已保存档案（已 gitignore）
```

所有 Agent 行为都在 `prompts/` 目录里定义。修改调研方式或输出风格，不需要改任何业务逻辑代码。

---

## 已知局限

Timbre 只能访问公开信息。薪酬结构、内部管理矛盾不在覆盖范围内。股权结构和融资细节在天眼查、企查查、Crunchbase、PitchBook 等平台有付费数据——配置对应平台的 cookie 后，browse_url 可直接获取。

LinkedIn 在中国的渗透率偏低，部分国内团队的组织信息会不完整。融资数据通常比实际晚披露 3 到 6 个月。这两点是数据源本身的天花板，工具层面无法解决。

付费媒体（晚点、The Information、36Kr Pro 等）已通过 Playwright + 浏览器 cookie 支持，配置 `BROWSER_COOKIES_FILE` 即可获取完整正文。

产品名与公司名不一致时，Stage 1 会通过多轮搜索自动确认实体；也可以在输入时直接附上创始人姓名或 `@` 补充文档进一步提高准确率。

---

## Tech Stack

Python · asyncio · Anthropic Claude · Tavily · Playwright · SQLite · Rich · Langfuse (optional)
