from __future__ import annotations
import asyncio
import os
from tavily import TavilyClient
from .registry import Tool, register

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


async def _handler(query: str, max_results: int = 8) -> dict:
    def _search():
        return _get_client().search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
        )

    result = await asyncio.to_thread(_search)
    return {
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
            }
            for r in result.get("results", [])
        ]
    }


web_search = Tool(
    name="web_search",
    description="Search the web for information about founders, companies, and industry context. Supports both Chinese and English queries.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Number of results (default 8)", "default": 8},
        },
        "required": ["query"],
    },
    handler=_handler,
)

register(web_search)
