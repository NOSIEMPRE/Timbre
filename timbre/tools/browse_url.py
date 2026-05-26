from __future__ import annotations
import asyncio
import os
from pathlib import Path
from .registry import Tool, register

MAX_CHARS = 50_000


def _parse_netscape_cookies(path: str) -> list[dict]:
    cookies = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                domain, _, path_, secure, expires, name, value = parts[:7]
                cookies.append({
                    "name": name, "value": value,
                    "domain": domain.lstrip("."), "path": path_,
                    "secure": secure.upper() == "TRUE", "sameSite": "None",
                })
    except Exception:
        pass
    return cookies


async def _handler(url: str) -> dict:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"content": "", "error": "playwright not installed — run: playwright install chromium", "url": url}

    cookies_file = os.getenv("BROWSER_COOKIES_FILE")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        if cookies_file and Path(cookies_file).exists():
            cookies = _parse_netscape_cookies(cookies_file)
            if cookies:
                await ctx.add_cookies(cookies)

        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            text = await page.evaluate("""() => {
                for (const el of document.querySelectorAll(
                    'nav, footer, header, aside, .ad, .ads, .advertisement, .paywall, script, style'
                )) el.remove();
                return document.body?.innerText || '';
            }""")
            return {"content": text[:MAX_CHARS], "error": None, "url": url}
        except Exception as e:
            return {"content": "", "error": str(e), "url": url}
        finally:
            await browser.close()


browse_url = Tool(
    name="browse_url",
    description=(
        "Fetch the full text of a URL using a headless browser. "
        "Use for complete articles, especially paywalled sources when cookies are configured."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
        },
        "required": ["url"],
    },
    handler=_handler,
)

register(browse_url, synthesis_only=True)
