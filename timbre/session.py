"""
timbre/session.py — Session-level token and cost accumulator.

Every LLM provider call reports its usage here. After a pipeline run
the CLI reads the summary and prints a cost line.

Usage:
    from timbre import session

    # At the start of a new research request:
    session.reset()

    # Inside each provider call (called automatically by providers):
    session.add_usage("claude-opus-4-7", input_tokens=1200, output_tokens=340)

    # After the pipeline finishes:
    s = session.summary()
    # → {"input_tokens": 14200, "output_tokens": 4100, "cost_usd": 0.17, "models": [...]}
"""
from __future__ import annotations

# ── Pricing table (USD per 1M tokens, as of 2026-05) ─────────────────────────
# (input_per_1M, output_per_1M)
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":              (5.00,  25.00),
    "claude-opus-4-6":              (5.00,  25.00),
    "claude-sonnet-4-6":            (3.00,  15.00),
    "claude-sonnet-4-5":            (3.00,  15.00),
    "claude-haiku-4-5":             (1.00,   5.00),
    "gpt-4o":                       (2.50,  10.00),
    "gpt-4o-mini":                  (0.15,   0.60),
    "gpt-4-turbo":                 (10.00,  30.00),
    "o1":                          (15.00,  60.00),
    "o1-mini":                      (3.00,  12.00),
    "o3-mini":                      (1.10,   4.40),
    "deepseek-chat":                (0.14,   0.28),
    "deepseek-reasoner":            (0.55,   2.19),
    "qwen-max":                     (0.40,   1.20),
    "qwen-plus":                    (0.08,   0.26),
    "glm-4":                        (0.10,   0.10),
    "moonshot-v1-8k":               (0.18,   0.18),
    "moonshot-v1-32k":              (0.40,   0.40),
    "gemini-2.0-flash":             (0.10,   0.40),
    "gemini-1.5-pro":               (1.25,   5.00),
    "grok-2-latest":                (2.00,  10.00),
}

# Prefix-based fallback for models not in the table above
_PREFIX_PRICING: list[tuple[str, tuple[float, float]]] = [
    ("claude-opus",   (5.00,  25.00)),
    ("claude-sonnet", (3.00,  15.00)),
    ("claude-haiku",  (1.00,   5.00)),
    ("gpt-4o-mini",   (0.15,   0.60)),
    ("gpt-4",         (2.50,  10.00)),
    ("o1-mini",       (3.00,  12.00)),
    ("o3",            (1.10,   4.40)),
    ("deepseek",      (0.14,   0.28)),
    ("qwen",          (0.40,   1.20)),
    ("glm",           (0.10,   0.10)),
    ("moonshot",      (0.18,   0.18)),
    ("gemini",        (0.10,   0.40)),
    ("llama",         (0.00,   0.00)),   # local / Ollama
]

# ── Module-level state ────────────────────────────────────────────────────────

# {model_name: {"input": N, "output": N}}
_buckets: dict[str, dict[str, int]] = {}


def reset() -> None:
    """Clear all accumulated usage. Call at the start of each research request."""
    _buckets.clear()


def add_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage for one LLM call. Thread-safe enough for asyncio."""
    if not model:
        return
    if model not in _buckets:
        _buckets[model] = {"input": 0, "output": 0}
    _buckets[model]["input"] += max(0, input_tokens or 0)
    _buckets[model]["output"] += max(0, output_tokens or 0)


def _price_for(model: str) -> tuple[float, float]:
    """Return (input_$/1M, output_$/1M) for a given model name."""
    m = model.lower().strip()
    if m in _PRICING:
        return _PRICING[m]
    for prefix, price in _PREFIX_PRICING:
        if m.startswith(prefix):
            return price
    return (1.00, 3.00)   # conservative unknown-model fallback


def cost_usd() -> float:
    """Total estimated cost in USD for the current session."""
    total = 0.0
    for model, counts in _buckets.items():
        inp, out = _price_for(model)
        total += (counts["input"] / 1_000_000) * inp
        total += (counts["output"] / 1_000_000) * out
    return total


def summary() -> dict:
    """
    Return a summary dict for display.

    Keys:
        input_tokens  — total input tokens across all models
        output_tokens — total output tokens across all models
        cost_usd      — estimated total cost in USD
        models        — list of model names used
        breakdown     — {model: {input, output, cost_usd}}
    """
    total_in = sum(v["input"] for v in _buckets.values())
    total_out = sum(v["output"] for v in _buckets.values())

    breakdown: dict[str, dict] = {}
    for model, counts in _buckets.items():
        inp_price, out_price = _price_for(model)
        model_cost = (
            (counts["input"] / 1_000_000) * inp_price
            + (counts["output"] / 1_000_000) * out_price
        )
        breakdown[model] = {
            "input": counts["input"],
            "output": counts["output"],
            "cost_usd": round(model_cost, 4),
        }

    return {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cost_usd": round(cost_usd(), 4),
        "models": list(_buckets.keys()),
        "breakdown": breakdown,
    }


def has_data() -> bool:
    """True if any usage has been recorded since the last reset()."""
    return bool(_buckets)
