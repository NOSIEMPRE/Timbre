import os
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider

_provider = None


def get_provider():
    global _provider
    if _provider is None:
        if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"):
            _provider = OpenAIProvider()
        else:
            _provider = AnthropicProvider()
    return _provider
