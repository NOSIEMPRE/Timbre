from __future__ import annotations
import os

_provider = None


def get_provider():
    global _provider
    if _provider is None:
        use_openai = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_KEY")
        if use_openai:
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError(
                    "OPENAI_API_KEY 未设置。请运行 `timbre config` 填入 API Key。"
                )
            from .openai_provider import OpenAIProvider
            _provider = OpenAIProvider()
        else:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "未找到 API Key。请运行 `timbre config` 完成配置。"
                )
            from .anthropic_provider import AnthropicProvider
            _provider = AnthropicProvider()
    return _provider
