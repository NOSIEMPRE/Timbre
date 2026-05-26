from __future__ import annotations
import os

_provider = None


def get_provider():
    global _provider
    if _provider is None:
        if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"):
            from .openai_provider import OpenAIProvider
            _provider = OpenAIProvider()
        else:
            from .anthropic_provider import AnthropicProvider
            _provider = AnthropicProvider()
    return _provider
