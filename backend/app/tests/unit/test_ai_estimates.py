"""Unit tests: deterministic token/cost estimates (Sprint M11.1)."""
from __future__ import annotations

import pytest

from app.application.ai.llm.estimates import estimate_cost_usd, estimate_tokens


class TestEstimateTokens:
    def test_empty_input_is_zero(self):
        assert estimate_tokens("") == 0
        # Pure arithmetic on code points: 3 chars -> ceil(3/4) = 1.
        assert estimate_tokens("   ") == 1

    def test_rounds_up_per_four_chars(self):
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("abcde") == 2
        assert estimate_tokens("a") == 1

    def test_deterministic_across_calls(self):
        text = "The quick brown fox jumps over the lazy dog." * 10
        assert estimate_tokens(text) == estimate_tokens(text)

    def test_unicode_counts_code_points(self):
        # Unicode is counted deterministically (code points), no exceptions.
        assert estimate_tokens("héllo—wörld") == estimate_tokens("héllo—wörld")


class TestEstimateCost:
    def test_zero_without_prices(self):
        assert estimate_cost_usd(input_tokens=1000, output_tokens=500) == 0.0

    def test_priced_call(self):
        cost = estimate_cost_usd(
            input_tokens=1000,
            output_tokens=2000,
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60,
        )
        assert cost == pytest.approx(0.15 + 1.2, abs=1e-6)

    def test_negative_values_rejected(self):
        with pytest.raises(ValueError):
            estimate_cost_usd(input_tokens=-1, output_tokens=0)
        with pytest.raises(ValueError):
            estimate_cost_usd(input_tokens=0, output_tokens=0, cost_per_1k_input=-0.1)

    def test_rounding_is_stable(self):
        cost = estimate_cost_usd(
            input_tokens=333,
            output_tokens=111,
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60,
        )
        assert cost == round(cost, 6)
