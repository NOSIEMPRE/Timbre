from __future__ import annotations
import asyncio
import os
from pathlib import Path
from .registry import Tool, register

MAX_CHARS = 40_000


async def _handler(file_path: str) -> dict:
    path = Path(file_path).expanduser()
    if not path.exists():
        return {"content": "", "error": f"File not found: {file_path}"}

    suffix = path.suffix.lower()

    def _read() -> dict:
        try:
            if suffix == ".pdf":
                import pdfplumber
                texts = []
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            texts.append(t)
                content = "\n\n".join(texts)
                return {"content": content[:MAX_CHARS], "pages": len(pdf.pages), "error": None}

            elif suffix in {".md", ".txt", ".text"}:
                content = path.read_text(encoding="utf-8", errors="replace")
                return {"content": content[:MAX_CHARS], "error": None}

            elif suffix == ".csv":
                import csv, io
                raw = path.read_text(encoding="utf-8", errors="replace")
                reader = csv.reader(io.StringIO(raw))
                rows = ["\t".join(row) for row in reader]
                content = "\n".join(rows)
                return {"content": content[:MAX_CHARS], "error": None}

            elif suffix == ".json":
                content = path.read_text(encoding="utf-8", errors="replace")
                return {"content": content[:MAX_CHARS], "error": None}

            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                return {"content": content[:MAX_CHARS], "error": None}

        except Exception as e:
            return {"content": "", "error": str(e)}

    return await asyncio.to_thread(_read)


read_file = Tool(
    name="read_file",
    description="Read a local file (PDF, Markdown, TXT, CSV, JSON). Returns the text content.",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute or relative path to the file"},
        },
        "required": ["file_path"],
    },
    handler=_handler,
)

register(read_file)
