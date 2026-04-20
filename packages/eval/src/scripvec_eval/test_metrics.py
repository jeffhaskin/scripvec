"""Tests for evaluation metrics."""

import pytest

from scripvec_eval.metrics import mrr_at_10, ndcg_at_10, percentile, recall_at_k


class TestRecallAtK:
    def test_perfect_recall(self) -> None:
        """All relevant docs in top k gives recall = 1.0."""
        retrieved = ["a", "b", "c"]
        relevant = {"a": 2, "b": 1}
        assert recall_at_k(retrieved, relevant, 3) == 1.0

    def test_partial_recall(self) -> None:
        """Half of relevant docs gives recall = 0.5."""
        retrieved = ["a", "x", "y"]
        relevant = {"a": 1, "b": 1}
        assert recall_at_k(retrieved, relevant, 3) == 0.5

    def test_no_recall(self) -> None:
        """No relevant docs in top k gives recall = 0.0."""
        retrieved = ["x", "y", "z"]
        relevant = {"a": 1, "b": 1}
        assert recall_at_k(retrieved, relevant, 3) == 0.0

    def test_empty_relevant_returns_zero(self) -> None:
        """Empty relevant set returns 0.0."""
        assert recall_at_k(["a", "b"], {}, 2) == 0.0

    def test_k_less_than_one_raises(self) -> None:
        """k < 1 raises ValueError."""
        with pytest.raises(ValueError, match="k must be at least 1"):
            recall_at_k(["a"], {"a": 1}, 0)


class TestNdcgAt10:
    def test_perfect_order_returns_one(self) -> None:
        """Perfect ranking gives nDCG = 1.0."""
        retrieved = ["a", "b", "c"]
        relevant = {"a": 2, "b": 1}
        assert ndcg_at_10(retrieved, relevant) == pytest.approx(1.0)

    def test_gain_formula_grade_2(self) -> None:
        """Grade 2 has gain = 2**2 - 1 = 3."""
        retrieved = ["a"]
        relevant = {"a": 2}
        assert ndcg_at_10(retrieved, relevant) == pytest.approx(1.0)

    def test_gain_formula_grade_1(self) -> None:
        """Grade 1 has gain = 2**1 - 1 = 1."""
        retrieved = ["a"]
        relevant = {"a": 1}
        assert ndcg_at_10(retrieved, relevant) == pytest.approx(1.0)

    def test_empty_relevant_returns_zero(self) -> None:
        """Empty relevant set returns 0.0."""
        assert ndcg_at_10(["a", "b"], {}) == 0.0

    def test_no_relevant_in_top_10(self) -> None:
        """No relevant docs in top 10 gives nDCG = 0.0."""
        retrieved = ["x"] * 10
        relevant = {"a": 2}
        assert ndcg_at_10(retrieved, relevant) == 0.0


class TestMrrAt10:
    def test_first_position(self) -> None:
        """Relevant doc at position 1 gives MRR = 1.0."""
        assert mrr_at_10(["a", "x", "y"], {"a": 1}) == 1.0

    def test_second_position(self) -> None:
        """Relevant doc at position 2 gives MRR = 0.5."""
        assert mrr_at_10(["x", "a", "y"], {"a": 1}) == 0.5

    def test_third_position(self) -> None:
        """Relevant doc at position 3 gives MRR = 1/3."""
        assert mrr_at_10(["x", "y", "a"], {"a": 1}) == pytest.approx(1.0 / 3)

    def test_not_in_top_10(self) -> None:
        """Relevant doc not in top 10 gives MRR = 0.0."""
        retrieved = ["x"] * 10 + ["a"]
        assert mrr_at_10(retrieved, {"a": 1}) == 0.0

    def test_empty_relevant_returns_zero(self) -> None:
        """Empty relevant set returns 0.0."""
        assert mrr_at_10(["a", "b"], {}) == 0.0


class TestPercentile:
    def test_median(self) -> None:
        """50th percentile is median."""
        samples = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(samples, 50) == 3.0

    def test_min(self) -> None:
        """0th percentile is minimum."""
        samples = [1.0, 2.0, 3.0]
        assert percentile(samples, 0) == 1.0

    def test_max(self) -> None:
        """100th percentile is maximum."""
        samples = [1.0, 2.0, 3.0]
        assert percentile(samples, 100) == 3.0

    def test_interpolation(self) -> None:
        """Interpolates between values."""
        samples = [0.0, 10.0]
        assert percentile(samples, 50) == 5.0

    def test_single_value(self) -> None:
        """Single value returns that value for any percentile."""
        assert percentile([42.0], 50) == 42.0

    def test_empty_samples_raises(self) -> None:
        """Empty samples raises ValueError."""
        with pytest.raises(ValueError, match="samples cannot be empty"):
            percentile([], 50)

    def test_p_below_zero_raises(self) -> None:
        """p < 0 raises ValueError."""
        with pytest.raises(ValueError, match="p must be in range"):
            percentile([1.0], -1)

    def test_p_above_100_raises(self) -> None:
        """p > 100 raises ValueError."""
        with pytest.raises(ValueError, match="p must be in range"):
            percentile([1.0], 101)
