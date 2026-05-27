#!/usr/bin/env python3
"""见微 · Timbre — interactive CLI"""
from __future__ import annotations
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load config: ~/.timbre/.env first, then local .env overrides
load_dotenv(Path.home() / ".timbre" / ".env")
load_dotenv()

from rich.console import Console
from rich.markup import escape

from timbre.pipelines.founder_research import run_founder_research
from timbre.memory.store import remember, list_all
from timbre.providers import get_provider
from timbre.eval.quality_check import quality_check

console = Console()

# ── Data directory ────────────────────────────────────────────────────────────

def get_output_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    subfolder = os.getenv("OBSIDIAN_SUBFOLDER", "Timbre")
    if vault:
        d = Path(vault) / subfolder
        d.mkdir(parents=True, exist_ok=True)
        return d
    # Default: ~/.timbre/profiles — works regardless of install location
    d = Path.home() / ".timbre" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── File helpers ──────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    if not s:
        return "unknown"
    return re.sub(r"[^\w一-鿿-]", "", str(s).lower().replace(" ", "-"))[:60]


def build_filename(entity: dict) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    f = entity.get("founder_en") or entity.get("founder") or "unknown"
    c = entity.get("company") or "unknown"
    return f"{slugify(f)}-{slugify(c)}-{date}.md"


def build_frontmatter(entity: dict) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    tags = ["founder-profile"]
    val = entity.get("valuation", "")
    try:
        v = float(re.sub(r"[^\d.]", "", val.replace("B", "000").replace("M", "")))
        if v >= 10000:
            tags.append("decacorn")
        elif v >= 1000:
            tags.append("unicorn")
    except Exception:
        pass

    lines = ["---", f'founder: "{entity.get("founder", "")}"']
    if entity.get("founder_en") and entity["founder_en"] != entity.get("founder"):
        lines.append(f'founder_en: "{entity["founder_en"]}"')
    lines += [f'company: "{entity.get("company", "")}"']
    if val:
        lines.append(f'valuation: "{val}"')
    lines += [
        f"created: {date}",
        "tags: [" + ", ".join(f'"{t}"' for t in tags) + "]",
        'source: "见微·Timbre"',
        "---", "",
    ]
    return "\n".join(lines)


def add_wiki_links(profile: str, entity: dict) -> str:
    result = profile
    targets = [entity.get("company", "")]
    en = entity.get("founder_en", "")
    if en and en != entity.get("founder"):
        targets.append(en)
    for target in targets:
        if not target or len(target) < 2:
            continue
        result = re.sub(
            rf"(?<!\[\[)\b{re.escape(target)}\b(?!\]\])",
            f"[[{target}]]", result, count=1,
        )
    return result


# ── Intent classification ─────────────────────────────────────────────────────

async def classify_intent(text: str, has_session: bool) -> str:
    VALID = {"research", "followup", "list", "memory", "help", "exit"}
    words = text.strip().split()

    # Fast-path: unambiguous exit commands
    if text.strip().lower() in ("exit", "quit", "退出", "再见", "拜拜"):
        return "exit"

    # Fast-path: short input with no question mark and no followup signals
    # → almost certainly a name or company, regardless of session state
    FOLLOWUP_SIGNALS = {"他", "她", "这", "那", "其", "更多", "详细",
                        "呢", "吗", "如何", "怎么", "融资", "团队", "联创",
                        "为什么", "什么时候", "多少", "哪里", "tell me more"}
    has_followup = any(s in text for s in FOLLOWUP_SIGNALS)
    if len(words) <= 3 and "?" not in text and "？" not in text and not has_followup:
        return "research"

    provider = get_provider()
    state = "（当前 session 已完成过一次研究）" if has_session else "（当前 session 尚未研究任何人）"
    raw = await provider.complete(
        system="你是一个意图分类器，只输出分类结果，不输出任何其他内容。",
        user=f"用户输入：「{text}」\n当前状态：{state}\n\n"
             "判断用户意图，从以下选项中选一个输出：\n"
             "- research   （想研究某个创始人或公司）\n"
             "- followup   （对刚才研究结果的追问，只有 session 里有研究结果时才选这个）\n"
             "- list       （查看已保存档案）\n"
             "- memory     （查看历史研究记录）\n"
             "- help       （需要帮助）\n"
             "- exit       （想退出）\n\n只输出一个单词。",
    )
    intent = raw.strip().lower().split()[0] if raw.strip() else "research"
    return intent if intent in VALID else "research"


# ── Follow-up QA ──────────────────────────────────────────────────────────────

async def answer_follow_up(question: str, session_ctx: dict) -> str:
    provider = get_provider()
    entity = session_ctx["entity"]
    return await provider.complete(
        system=f"你是一位一级市场研究员，刚完成对「{entity.get('founder')}（{entity.get('company')}）」的调研。"
               "基于以下档案回答追问，档案中无相关信息请明确说明，不要捏造。",
        user=f"档案内容：\n\n{session_ctx['profile']}\n\n用户追问：{question}",
    )


# ── @ref parsing ──────────────────────────────────────────────────────────────

def extract_refs(text: str) -> tuple[str, list[str], list[str]]:
    files, urls = [], []

    def _replace(m):
        ref = m.group(1)
        (urls if ref.startswith("http") else files).append(ref)
        return ""

    query = re.sub(r"@(\S+)", _replace, text).strip()
    return query, files, urls


# ── Display ───────────────────────────────────────────────────────────────────

def make_send():
    def send(event: dict):
        t = event.get("type")
        if t == "stage":
            if event.get("status") == "start":
                console.print(f"  [cyan]▸[/cyan] {event.get('label', event.get('name', ''))}", end="  ")
            elif event.get("status") == "done":
                result = event.get("result")
                if result:
                    conf = {"high": 90, "medium": 70}.get(result.get("confidence", ""), 50)
                    founder_d = result.get("founder") or result.get("founder_en") or "未识别"
                    company_d = result.get("company") or "未识别"
                    console.print(f"\n  [dim]→ {founder_d} · {company_d}  (置信度 {conf}%)[/dim]")
                else:
                    console.print()
        elif t == "tool_start":
            console.print("[dim].[/dim]", end="")
        elif t == "search_summary":
            raw, used = event.get("raw", 0), event.get("used", 0)
            color = "green" if used > 0 else "red"
            console.print(f"\n  [dim]搜索原始结果 {raw} 条 → 有效来源 [{color}]{used}[/{color}] 条[/dim]")
        elif t == "plan_ready":
            dims = event.get("plan", {}).get("dimensions", [])
            total = sum(len(d.get("queries", [])) for d in dims)
            labels = " · ".join(d.get("label", d.get("name", "")) for d in dims)
            console.print(f"\n  [dim]计划：{labels}  共 {total} 条搜索[/dim]")
        elif t == "memory_hit":
            e = event.get("entity", {})
            console.print(f"\n  [yellow]↩[/yellow]  [dim]发现已有记录：{e.get('founder')} · {e.get('company')}（{e.get('last_researched', '')}）[/dim]")
        elif t == "search_error":
            console.print(f"\n  [red]✗[/red]  [dim]搜索失败：{event.get('error', '')}[/dim]")
        elif t == "context_error":
            console.print(f"\n  [yellow]⚠[/yellow]  [dim]读取失败：{event.get('path')} — {event.get('error')}[/dim]")
        elif t == "eval":
            m = event.get("metrics", {})
            score = m.get("score", 0)
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            console.print(f"\n  [bold]质量评分[/bold]  [{color}]{score}分[/{color}]  字数 {m.get('word_count', 0)}  来源 {m.get('url_count', 0)}")
            for issue in m.get("issues", []):
                console.print(f"  [yellow]⚠[/yellow]  {issue}")
    return send


def list_profiles():
    d = get_output_dir()
    files = sorted([f for f in d.iterdir() if f.suffix == ".md"], reverse=True)
    if not files:
        console.print("  [dim]还没有保存的档案。[/dim]")
        return
    console.print(f"  [bold]已保存档案 ({len(files)}):[/bold]\n")
    for f in files:
        console.print(f"  [green]·[/green] {f.stem}  [dim]({round(f.stat().st_size / 1024)} KB)[/dim]")


def list_memory():
    entries = list_all()
    if not entries:
        console.print("  [dim]还没有研究记录。[/dim]")
        return
    console.print(f"  [bold]研究记录 ({len(entries)}):[/bold]\n")
    for e in entries:
        exists = e.get("profile_path") and Path(e["profile_path"]).exists()
        dot = "[green]·[/green]" if exists else "[dim]·[/dim]"
        console.print(f"  {dot} {e.get('founder')} · {e.get('company')}  [dim]{e.get('last_researched', '')}[/dim]")


# ── Main query handler ────────────────────────────────────────────────────────

async def handle_query(text: str, session_ctx: dict | None) -> dict | None:
    text = text.strip()
    if not text:
        return session_ctx

    console.print()
    console.print("  [dim]…[/dim]", end="\r")
    intent = await classify_intent(text, session_ctx is not None)
    console.print("     ", end="\r")

    if intent == "exit":
        console.print("  [dim]再见。[/dim]\n")
        sys.exit(0)

    if intent == "list":
        console.print(); list_profiles(); console.print()
        return session_ctx

    if intent == "memory":
        console.print(); list_memory(); console.print()
        return session_ctx

    if intent == "help":
        console.print("""
  [bold]直接说你想研究谁，不用记命令。[/bold]

  [dim]发起研究[/dim]
    帮我看看 xx 公司的创始人
    某某 AI 公司 CEO 的背景
    xx 创始人 @./尽调材料.pdf @https://...

  [dim]追问当前档案[/dim]
    他的融资情况能详细说说吗
    联创团队呢

  [dim]其他[/dim]
    查看档案  ·  历史记录  ·  退出
""")
        return session_ctx

    if intent == "followup" and session_ctx:
        send = make_send()
        send({"type": "stage", "name": "followup", "status": "start", "label": "基于档案回答中"})
        answer = await answer_follow_up(text, session_ctx)
        send({"type": "stage", "name": "followup", "status": "done"})
        console.print("\n" + answer + "\n")
        return session_ctx

    # Research
    query, files, urls = extract_refs(text)
    if files:
        console.print(f"  [dim]附加文档：{'、'.join(files)}[/dim]")
    if urls:
        console.print(f"  [dim]附加链接：{'、'.join(urls)}[/dim]")

    send = make_send()
    result = await run_founder_research(query or text, send, files, urls)
    profile, entity = result["profile"], result["entity"]

    metrics = quality_check(profile, entity)
    send({"type": "eval", "metrics": metrics})

    out_dir = get_output_dir()
    filename = build_filename(entity) if entity else f"profile-{int(datetime.now().timestamp())}.md"
    filepath = out_dir / filename
    content = build_frontmatter(entity) + add_wiki_links(profile, entity) if entity else profile
    filepath.write_text(content, encoding="utf-8")

    if entity:
        remember(entity, str(filepath))

    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    display = f"{vault}/{os.getenv('OBSIDIAN_SUBFOLDER', 'Timbre')}/{filename}" if vault else str(filepath)
    console.print(f"\n  [green]✓[/green]  已保存至 [bold]{display}[/bold]\n")

    return {"entity": entity, "profile": profile, "profile_path": str(filepath)} if entity else session_ctx


# ── Entry points ──────────────────────────────────────────────────────────────

async def main():
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    dest = f"[dim]Obsidian: {vault}/{os.getenv('OBSIDIAN_SUBFOLDER', 'Timbre')}[/dim]" if vault \
        else f"[dim]~/.timbre/profiles/[/dim]"

    console.print(f"\n  [bold cyan]见微 · Timbre[/bold cyan]  {dest}")
    console.print("  [dim]输入创始人姓名或公司名，开始调研。[/dim]\n")

    session_ctx = None
    while True:
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\x1b[36mtimbre\x1b[0m › ")
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n\n  [dim]再见。[/dim]\n")
            break
        try:
            session_ctx = await handle_query(text, session_ctx)
        except Exception as e:
            console.print(f"\n  [red]✗[/red]  {escape(str(e))}\n")


_PROVIDERS = [
    ("anthropic",  "Anthropic Claude",   "console.anthropic.com/settings/keys",       None),
    ("openai",     "OpenAI",             "platform.openai.com/api-keys",               "https://api.openai.com/v1"),
    ("deepseek",   "DeepSeek",           "platform.deepseek.com/api-keys",             "https://api.deepseek.com/v1"),
    ("qwen",       "通义千问 Qwen",       "dashscope.aliyuncs.com",                     "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ("glm",        "智谱 GLM",            "open.bigmodel.cn",                           "https://open.bigmodel.cn/api/paas/v4"),
    ("kimi",       "Kimi (Moonshot AI)", "platform.moonshot.cn",                       "https://api.moonshot.cn/v1"),
    ("grok",       "Grok (xAI)",         "console.x.ai",                               "https://api.x.ai/v1"),
    ("gemini",     "Gemini (Google)",    "aistudio.google.com/app/apikey",             "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ("ollama",     "Ollama (本地部署)",   "ollama.ai",                                  "http://localhost:11434/v1"),
    ("other",      "其他 OpenAI-compatible API", "",                                   None),
]

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai":    "gpt-4o",
    "deepseek":  "deepseek-chat",
    "qwen":      "qwen-max",
    "glm":       "glm-4",
    "kimi":      "moonshot-v1-8k",
    "grok":      "grok-2-latest",
    "gemini":    "gemini-2.0-flash",
    "ollama":    "llama3.1:8b",
    "other":     "",
}


def config():
    """Interactive first-run configuration wizard."""
    import subprocess

    cfg_path = Path.home() / ".timbre" / ".env"
    cfg_path.parent.mkdir(exist_ok=True)

    existing: dict[str, str] = {}
    if cfg_path.exists():
        for line in cfg_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    console.print("\n  [bold cyan]见微 · Timbre[/bold cyan]  配置向导\n")

    def ask(prompt: str, default: str = "", secret: bool = False) -> str:
        hint = f" [dim](回车保留现有值)[/dim]" if default else " [dim](回车跳过)[/dim]"
        console.print(f"  {prompt}{hint}")
        val = input("  › ").strip()
        return val or default

    # ── Step 1: Choose provider ───────────────────────────────────────────────
    console.print("  [bold]选择 AI 模型提供商：[/bold]\n")
    for i, (_, label, url, _) in enumerate(_PROVIDERS, 1):
        url_hint = f"  [dim]{url}[/dim]" if url else ""
        console.print(f"  [cyan]{i:2}.[/cyan] {label}{url_hint}")
    console.print()

    cur_provider = "anthropic"
    if existing.get("OPENAI_BASE_URL"):
        for key, _, _, base_url in _PROVIDERS:
            if base_url and existing["OPENAI_BASE_URL"].startswith(base_url.split("/v")[0]):
                cur_provider = key
                break
        else:
            cur_provider = "other"

    cur_idx = next((i for i, (k, *_) in enumerate(_PROVIDERS, 1) if k == cur_provider), 1)
    console.print(f"  选择编号 [dim](当前: {cur_idx})[/dim]")
    raw = input("  › ").strip()
    idx = int(raw) - 1 if raw.isdigit() and 1 <= int(raw) <= len(_PROVIDERS) else cur_idx - 1
    provider_key, provider_label, _, base_url = _PROVIDERS[idx]

    console.print()

    # ── Step 2: API key ───────────────────────────────────────────────────────
    if provider_key == "anthropic":
        cur_key = existing.get("ANTHROPIC_API_KEY", "")
        api_key = ask("Anthropic API Key", default=cur_key)
    elif provider_key == "ollama":
        api_key = "ollama"
        console.print("  [dim]Ollama 不需要 API Key，跳过。[/dim]")
    else:
        cur_key = existing.get("OPENAI_API_KEY", "")
        api_key = ask(f"{provider_label} API Key", default=cur_key)

    if provider_key == "other":
        cur_url = existing.get("OPENAI_BASE_URL", "")
        base_url = ask("Base URL (e.g. https://api.xxx.com/v1)", default=cur_url)

    # ── Step 3: Model name ────────────────────────────────────────────────────
    default_model = _DEFAULT_MODELS.get(provider_key, "")
    cur_model = existing.get("MODEL", default_model)
    console.print()
    model = ask(f"模型名称", default=cur_model)

    # ── Step 4: Tavily ────────────────────────────────────────────────────────
    console.print()
    cur_tavily = existing.get("TAVILY_API_KEY", "")
    tavily_key = ask("Tavily API Key  [dim]app.tavily.com[/dim]", default=cur_tavily)

    # ── Step 5: Optional ─────────────────────────────────────────────────────
    console.print()
    cur_obsidian = existing.get("OBSIDIAN_VAULT_PATH", "")
    obsidian_path = ask("Obsidian Vault 路径  [dim](可选)[/dim]", default=cur_obsidian)

    cur_cookies = existing.get("BROWSER_COOKIES_FILE", "")
    cookies_file = ask("cookies.txt 路径  [dim](付费内容访问，可选)[/dim]", default=cur_cookies)

    # ── Write config ──────────────────────────────────────────────────────────
    lines = []
    if provider_key == "anthropic":
        lines.append(f"ANTHROPIC_API_KEY={api_key}")
    else:
        lines.append(f"OPENAI_API_KEY={api_key}")
        if base_url:
            lines.append(f"OPENAI_BASE_URL={base_url}")
    if model:
        lines.append(f"MODEL={model}")
    if tavily_key:
        lines.append(f"TAVILY_API_KEY={tavily_key}")
    if obsidian_path:
        lines.append(f"OBSIDIAN_VAULT_PATH={obsidian_path}")
    if cookies_file:
        lines.append(f"BROWSER_COOKIES_FILE={cookies_file}")

    cfg_path.write_text("\n".join(lines) + "\n")
    console.print(f"\n  [green]✓[/green]  配置已保存至 [bold]{cfg_path}[/bold]\n")

    # ── Install Playwright browsers ───────────────────────────────────────────
    console.print("  [dim]正在安装 Playwright 浏览器（首次需要约 1 分钟）…[/dim]")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  [green]✓[/green]  Playwright chromium 安装完成")
    else:
        console.print(f"  [yellow]⚠[/yellow]  Playwright 安装失败：{result.stderr.strip()[:200]}")
        console.print("  可手动运行：[bold]playwright install chromium[/bold]")

    console.print("\n  运行 [bold cyan]timbre[/bold cyan] 开始使用。\n")


def main_sync():
    if len(sys.argv) > 1 and sys.argv[1] == "config":
        config()
    else:
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    main_sync()
