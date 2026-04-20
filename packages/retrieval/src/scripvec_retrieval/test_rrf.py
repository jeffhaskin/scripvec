"""Tests for Reciprocal Rank Fusion."""

import pytest

from scripvec_retrieval.rrf import rrf


class TestRRFFormula:
    """Test RRF score calculation on known inputs."""

    def test_single_source_bm25_only(self) -> None:
        """Single item from BM25 gets score 1/(k+1)."""
        result = rrf([("verse-a", 1.0)], [], k=60, top_k=10)
        assert len(result) == 1
        assert result[0][0] == "verse-a"
        assert result[0][1] == pytest.approx(1.0 / 61)

    def test_single_source_dense_only(self) -> None:
        """Single item from dense gets score 1/(k+1)."""
        result = rrf([], [("verse-b", 1.0)], k=60, top_k=10)
        assert len(result) == 1
        assert result[0][0] == "verse-b"
        assert result[0][1] == pytest.approx(1.0 / 61)

    def test_overlapping_results_sum_scores(self) -> None:
        """Item in both lists gets sum of reciprocal ranks."""
        result = rrf([("verse-a", 1.0)], [("verse-a", 1.0)], k=60, top_k=10)
        assert len(result) == 1
        assert result[0][0] == "verse-a"
        assert result[0][1] == pytest.approx(2.0 / 61)

    def test_different_ranks_in_each_source(self) -> None:
        """Item at different ranks gets correct sum."""
        bm25 = [("verse-a", 1.0), ("verse-b", 0.9)]
        dense = [("verse-b", 1.0), ("verse-a", 0.9)]
        result = rrf(bm25, dense, k=60, top_k=10)

        scores = {vid: score for vid, score in result}
        expected_a = 1.0 / 61 + 1.0 / 62
        expected_b = 1.0 / 62 + 1.0 / 61
        assert scores["verse-a"] == pytest.approx(expected_a)
        assert scores["verse-b"] == pytest.approx(expected_b)


class TestTiebreaking:
    """Test deterministic tiebreaking by verse_id ascending."""

    def test_ties_broken_by_verse_id_ascending(self) -> None:
        """When scores tie, earlier verse_id comes first."""
        bm25 = [("z-verse", 1.0)]
        dense = [("a-verse", 1.0)]
        result = rrf(bm25, dense, k=60, top_k=10)

        assert result[0][0] == "a-verse"
        assert result[1][0] == "z-verse"
        assert result[0][1] == result[1][1]

    def test_equal_rrf_scores_alphabetical_order(self) -> None:
        """Items with identical RRF scores sort alphabetically."""
        bm25 = [("verse-c", 1.0)]
        dense = [("verse-a", 1.0)]
        result = rrf(bm25, dense, k=60, top_k=10)

        assert result[0][0] == "verse-a"
        assert result[1][0] == "verse-c"


class TestTopKTruncation:
    """Test top_k limits output size."""

    def test_truncates_to_top_k(self) -> None:
        """Only top_k results returned."""
        bm25 = [(f"verse-{i}", 1.0) for i in range(20)]
        result = rrf(bm25, [], k=60, top_k=5)
        assert len(result) == 5

    def test_returns_fewer_than_top_k_if_not_enough(self) -> None:
        """Returns all items if fewer than top_k exist."""
        result = rrf([("verse-a", 1.0), ("verse-b", 0.9)], [], k=60, top_k=10)
        assert len(result) == 2


class TestDisjointInputs:
    """Test RRF with non-overlapping inputs."""

    def test_disjoint_inputs_all_included(self) -> None:
        """Items from both lists included even without overlap."""
        bm25 = [("verse-a", 1.0), ("verse-b", 0.9)]
        dense = [("verse-c", 1.0), ("verse-d", 0.9)]
        result = rrf(bm25, dense, k=60, top_k=10)

        verse_ids = {vid for vid, _ in result}
        assert verse_ids == {"verse-a", "verse-b", "verse-c", "verse-d"}

    def test_disjoint_inputs_correct_scores(self) -> None:
        """Disjoint items each get score from their source only."""
        bm25 = [("verse-a", 1.0)]
        dense = [("verse-b", 1.0)]
        result = rrf(bm25, dense, k=60, top_k=10)

        scores = {vid: score for vid, score in result}
        assert scores["verse-a"] == pytest.approx(1.0 / 61)
        assert scores["verse-b"] == pytest.approx(1.0 / 61)


class TestValueErrors:
    """Test ValueError on invalid arguments."""

    def test_k_less_than_one_raises(self) -> None:
        """k < 1 raises ValueError."""
        with pytest.raises(ValueError, match="k must be >= 1"):
            rrf([], [], k=0, top_k=10)

    def test_k_negative_raises(self) -> None:
        """Negative k raises ValueError."""
        with pytest.raises(ValueError, match="k must be >= 1"):
            rrf([], [], k=-5, top_k=10)

    def test_top_k_less_than_one_raises(self) -> None:
        """top_k < 1 raises ValueError."""
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            rrf([], [], k=60, top_k=0)

    def test_top_k_negative_raises(self) -> None:
        """Negative top_k raises ValueError."""
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            rrf([], [], k=60, top_k=-1)


class TestDeterminism:
    """Test that RRF produces deterministic results."""

    def test_repeated_calls_same_result(self) -> None:
        """Multiple calls with same input produce identical output."""
        bm25 = [("verse-c", 1.0), ("verse-a", 0.9), ("verse-b", 0.8)]
        dense = [("verse-b", 1.0), ("verse-d", 0.9), ("verse-a", 0.8)]

        result1 = rrf(bm25, dense, k=60, top_k=10)
        result2 = rrf(bm25, dense, k=60, top_k=10)

        assert result1 == result2
