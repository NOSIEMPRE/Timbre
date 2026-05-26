"""
Optional Langfuse observability layer.
If LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY are set, traces every LLM call.
Otherwise all functions are no-ops — zero overhead, zero errors.
"""
from __future__ import annotations
import os
from typing import Any, Optional

_lf: Optional[Any] = None


def _client():
    global _lf
    if _lf is None and os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse import Langfuse
            _lf = Langfuse(
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
        except ImportError:
            pass
    return _lf


class _Null:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def span(self, **__): return _Null()
    def generation(self, **__): return _Null()
    def update(self, **__): return self
    def end(self, **__): return self
    def flush(self): pass


def trace(name: str, input: dict | None = None, metadata: dict | None = None):
    lf = _client()
    if lf:
        return lf.trace(name=name, input=input, metadata=metadata)
    return _Null()


def generation(trace_obj, name: str, model: str, input: list, output: str = "",
               usage: dict | None = None):
    if isinstance(trace_obj, _Null):
        return
    try:
        trace_obj.generation(name=name, model=model, input=input, output=output, usage=usage)
    except Exception:
        pass


def flush():
    lf = _client()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass
