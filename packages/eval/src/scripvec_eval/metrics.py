"""Evaluation metrics for retrieval quality: recall@k, nDCG@10, MRR@10, percentile."""

from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: dict[str, int], k: int) -> float:
    """Compute recall at k.

    Args:
        retrieved: Ordered list of retrieved document IDs.
        relevant: Dict mapping relevant doc IDs to grade (1 or 2). Absence = 0.
        k: Cutoff for retrieved list.

    Returns:
        Fraction of relevant documents retrieved in top k.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    if not relevant:
        return 0.0

    top_k = set(retrieved[:k])
    relevant_set = set(relevant.keys())
    return len(top_k & relevant_set) / len(relevant_set)


def ndcg_at_10(retrieved: list[str], relevant: dict[str, int]) -> float:
    """Compute nDCG@10 with gain = 2**grade - 1.

    Args:
        retrieved: Ordered list of retrieved document IDs.
        relevant: Dict mapping relevant doc IDs to grade (1 or 2). Absence = 0.

    Returns:
        Normalized Discounted Cumulative Gain at 10.
    """
    if not relevant:
        return 0.0

    def gain(grade: int) -> float:
        return float(2**grade - 1)

    def dcg(docs: list[str], grades: dict[str, int], k: int) -> float:
        total = 0.0
        for i, doc in enumerate(docs[:k]):
            grade = grades.get(doc, 0)
            if grade > 0:
                total += gain(grade) / math.log2(i + 2)
        return total

    actual_dcg = dcg(retrieved, relevant, 10)

    ideal_order = sorted(relevant.keys(), key=lambda d: relevant[d], reverse=True)
    ideal_dcg = dcg(ideal_order, relevant, 10)

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def mrr_at_10(retrieved: list[str], relevant: dict[str, int]) -> float:
    """Compute Mean Reciprocal Rank at 10.

    Args:
        retrieved: Ordered list of retrieved document IDs.
        relevant: Dict mapping relevant doc IDs to grade (1 or 2). Absence = 0.

    Returns:
        Reciprocal of the rank of the first relevant document in top 10, or 0.
    """
    if not relevant:
        return 0.0

    for i, doc in enumerate(retrieved[:10]):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def percentile(samples: list[float], p: float) -> float:
    """Compute the p-th percentile of samples using linear interpolation.

    Args:
        samples: List of numeric values.
        p: Percentile in range [0, 100].

    Returns:
        The p-th percentile value.
    """
    if not samples:
        raise ValueError("samples cannot be empty")
    if p < 0 or p > 100:
        raise ValueError("p must be in range [0, 100]")

    sorted_samples = sorted(samples)
    n = len(sorted_samples)

    if n == 1:
        return sorted_samples[0]

    rank = (p / 100) * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    weight = rank - lower

    return sorted_samples[lower] * (1 - weight) + sorted_samples[upper] * weight
