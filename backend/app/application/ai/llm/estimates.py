"""Deterministic token & cost estimation (Sprint M11.1).

The single source of truth for token/cost estimates used by every gateway
until real adapters report vendor usage. Doctrine (from the M11 blueprint):

- **No tokenizer dependency**: a stable chars-per-token approximation,
  identical across processes and CI, matching the assistant context
  builder's char-budget approach.
- **Honest zeros**: with no cost table configured, estimates are 0.0 —
  never fabricated prices.
"""
from __future__ import annotations

#: Approximation: one token ≈ 4 characters (industry-standard heuristic).
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate: ``ceil(len(text) / 4)``.

    Empty/whitespace-only input yields 0. Stable across processes and
    platforms (pure arithmetic on Unicode code points).
    """
    return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    cost_per_1k_input: float = 0.0,
    cost_per_1k_output: float = 0.0,
) -> float:
    """Estimated USD cost of one call from per-1k-token prices.

    Both token counts must be >= 0; prices must be >= 0. With no prices
    configured the estimate is 0.0 (honest unknown, never fabricated).
    The result is rounded to 6 decimals for stable output.
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be >= 0.")
    if cost_per_1k_input < 0 or cost_per_1k_output < 0:
        raise ValueError("Costs must be >= 0.")
    cost = (
        input_tokens / 1000.0 * cost_per_1k_input
        + output_tokens / 1000.0 * cost_per_1k_output
    )
    return round(cost, 6)


__all__ = ["estimate_cost_usd", "estimate_tokens"]
