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

load_dotenv(Path.home() / ".timbre" / ".env")
load_dotenv()  # local .env overrides

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.text import Text

from pipelines.founder_research import run_founder_research
from memory.store import remember, list_all, recall
from providers import get_provider
from eval.quality_check import quality_check

console = Console()

# ── Output directory ──────────────────────────────────────────────────────────

def get_output_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    subfolder = os.getenv("OBSIDIAN_SUBFOLDER", "Timbre")
    if vault:
        d = Path(vault) / subfolder
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = Path(__file__).parent / "profiles"
    d.mkdir(exist_ok=True)
    return d


# ── File helpers ──────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    return re.sub(r"[^\w一-鿿-]", "", s.lower().replace(" ", "-"))[:60]


def build_filename(entity: dict) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    f = entity.get("founder_en") or entity.get("founder", "unknown")
    c = entity.get("company", "unknown")
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

    lines = [
        "---",
        f'founder: "{entity.get("founder", "")}"',
    ]
    if entity.get("founder_en") and entity["founder_en"] != entity.get("founder"):
        lines.append(f'founder_en: "{entity["founder_en"]}"')
    lines += [
        f'company: "{entity.get("company", "")}"',
    ]
    if val:
        lines.append(f'valuation: "{val}"')
    lines += [
        f"created: {date}",
        "tags: [" + ", ".join(f'"{t}"' for t in tags) + "]",
        'source: "见微·Timbre"',
        "---",
        "",
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
        escaped = re.escape(target)
        result = re.sub(
            rf"(?<!\[\[)\b{escaped}\b(?!\]\])",
            f"[[{target}]]",
            result,
            count=1,
        )
    return result


# ── Intent classification ─────────────────────────────────────────────────────

async def classify_intent(text: str, has_session: bool) -> str:
    provider = get_provider()
    state = "（当前 session 已完成过一次研究）" if has_session else "（当前 session 尚未研究任何人）"
    raw = await provider.complete(
        system="你是一个意图分类器，只输出分类结果，不输出任何其他内容。",
        user=f"""用户输入：「{text}」
当前状态：{state}

判断用户意图，从以下选项中选一个输出：
- research   （想研究某个创始人或公司）
- followup   （对刚才研究结果的追问或要求补充，只有 session 里有研究结果时才选这个）
- list       （查看已保存档案）
- memory     （查看历史研究记录）
- help       （需要帮助或想了解用法）
- exit       （想退出）

只输出一个单词。""",
    )
    return raw.strip().lower().split()[0] if raw.strip() else "research"


# ── Follow-up QA ──────────────────────────────────────────────────────────────

async def answer_follow_up(question: str, session_ctx: dict) -> str:
    provider = get_provider()
    entity = session_ctx["entity"]
    profile = session_ctx["profile"]
    return await provider.complete(
        system=f"你是一位一级市场研究员，刚刚完成了对「{entity.get('founder')}（{entity.get('company')}）」的调研。"
               "请基于以下档案回答用户追问，如档案中无相关信息请明确说明，不要捏造。",
        user=f"档案内容：\n\n{profile}\n\n用户追问：{question}",
    )


# ── @ref parsing ──────────────────────────────────────────────────────────────

def extract_refs(text: str) -> tuple[str, list[str], list[str]]:
    files, urls = [], []

    def _replace(m):
        ref = m.group(1)
        if ref.startswith("http://") or ref.startswith("https://"):
            urls.append(ref)
        else:
            files.append(ref)
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
                    founder = result.get("founder", "")
                    company = result.get("company", "")
                    conf = int((result.get("confidence") == "high" and 90) or
                               (result.get("confidence") == "medium" and 70) or 50)
                    console.print(f"\n  [dim]→ {founder} · {company}  (置信度 {conf}%)[/dim]")
                else:
                    console.print()
        elif t == "tool_start":
            console.print("[dim].[/dim]", end="")
        elif t == "plan_ready":
            dims = event.get("plan", {}).get("dimensions", [])
            total = sum(len(d.get("queries", [])) for d in dims)
            labels = " · ".join(d.get("label", d.get("name", "")) for d in dims)
            console.print(f"\n  [dim]计划：{labels}  共 {total} 条搜索[/dim]")
        elif t == "memory_hit":
            e = event.get("entity", {})
            console.print(f"\n  [yellow]↩[/yellow]  [dim]发现已有记录：{e.get('founder')} · {e.get('company')}（{e.get('last_researched', '')}）[/dim]")
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
    files = sorted([f for f in d.iterdir() if f.suffix == ".md" and f.name != ".gitkeep"], reverse=True)
    if not files:
        console.print("  [dim]还没有保存的档案。[/dim]")
        return
    console.print(f"  [bold]已保存档案 ({len(files)}):[/bold]\n")
    for f in files:
        size = round(f.stat().st_size / 1024)
        console.print(f"  [green]·[/green] {f.stem}  [dim]({size} KB)[/dim]")


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

    # Classify intent
    console.print("  [dim]…[/dim]", end="\r")
    intent = await classify_intent(text, session_ctx is not None)
    console.print("     ", end="\r")  # clear ellipsis

    if intent == "exit":
        console.print("  [dim]再见。[/dim]\n")
        sys.exit(0)

    if intent == "list":
        console.print()
        list_profiles()
        console.print()
        return session_ctx

    if intent == "memory":
        console.print()
        list_memory()
        console.print()
        return session_ctx

    if intent == "help":
        console.print("""
  [bold]Timbre 会理解你的自然语言，直接说你想做什么就好。[/bold]

  [dim]研究：[/dim]
    帮我研究一下梁文锋
    DeepSeek 的创始人背景
    月之暗面 @./notes.md @https://...

  [dim]追问（研究完之后）：[/dim]
    他的融资情况能详细说说吗
    联创团队背景呢

  [dim]其他：[/dim]
    查看我保存的档案
    看看历史研究记录
    退出
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
    profile = result["profile"]
    entity = result["entity"]

    # Quality eval
    metrics = quality_check(profile, entity)
    send({"type": "eval", "metrics": metrics})

    # Save to disk
    out_dir = get_output_dir()
    filename = build_filename(entity) if entity else f"profile-{int(datetime.now().timestamp())}.md"
    filepath = out_dir / filename
    content = build_frontmatter(entity) + add_wiki_links(profile, entity) if entity else profile
    filepath.write_text(content, encoding="utf-8")

    if entity:
        remember(entity, str(filepath))

    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    if vault:
        display = f"{vault}/{os.getenv('OBSIDIAN_SUBFOLDER', 'Timbre')}/{filename}"
    else:
        display = f"profiles/{filename}"

    console.print(f"\n  [green]✓[/green]  已保存至 [bold]{display}[/bold]\n")
    return {"entity": entity, "profile": profile, "profile_path": str(filepath)} if entity else session_ctx


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    if vault:
        dest = f"[dim]Obsidian: {vault}/{os.getenv('OBSIDIAN_SUBFOLDER', 'Timbre')}[/dim]"
    else:
        dest = "[dim]→ profiles/[/dim]"

    console.print(f"\n  [bold cyan]见微 · Timbre[/bold cyan]  {dest}")
    console.print("  [dim]直接说你想研究谁，或者研究完之后继续追问。[/dim]\n")

    session_ctx = None

    while True:
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: input("\x1b[36mtimbre\x1b[0m › "),
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n\n  [dim]再见。[/dim]\n")
            break

        try:
            session_ctx = await handle_query(text, session_ctx)
        except Exception as e:
            console.print(f"\n  [red]✗[/red]  {escape(str(e))}\n")


def config():
    """Interactive first-run configuration wizard."""
    cfg_path = Path.home() / ".timbre" / ".env"
    cfg_path.parent.mkdir(exist_ok=True)

    # Load existing values
    existing: dict[str, str] = {}
    if cfg_path.exists():
        for line in cfg_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    console.print("\n  [bold cyan]见微 · Timbre[/bold cyan]  配置向导\n")

    def ask(key: str, prompt: str, required: bool = True, default: str = "") -> str:
        cur = existing.get(key, default)
        hint = f" [dim](当前: {cur[:12]}…)[/dim]" if cur else ""
        console.print(f"  {prompt}{hint}")
        val = input("  › ").strip()
        return val or cur

    anthropic_key = ask("ANTHROPIC_API_KEY", "Anthropic API Key [dim](必填)[/dim]")
    tavily_key    = ask("TAVILY_API_KEY",    "Tavily API Key   [dim](必填)[/dim]")
    obsidian_path = ask("OBSIDIAN_VAULT_PATH", "Obsidian Vault 路径 [dim](可选，回车跳过)[/dim]", required=False)
    cookies_file  = ask("BROWSER_COOKIES_FILE", "cookies.txt 路径  [dim](可选，用于付费内容)[/dim]", required=False)

    lines = [
        f"ANTHROPIC_API_KEY={anthropic_key}",
        f"TAVILY_API_KEY={tavily_key}",
    ]
    if obsidian_path:
        lines.append(f"OBSIDIAN_VAULT_PATH={obsidian_path}")
    if cookies_file:
        lines.append(f"BROWSER_COOKIES_FILE={cookies_file}")

    cfg_path.write_text("\n".join(lines) + "\n")
    console.print(f"\n  [green]✓[/green]  配置已保存至 [bold]{cfg_path}[/bold]")
    console.print("  运行 [bold]timbre[/bold] 开始使用。\n")


def main_sync():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "config":
        config()
    else:
        asyncio.run(main())


if __name__ == "__main__":
    main_sync()
