"""scripvec retrieval — embeddings, vector index, BM25, hybrid, query path."""

from .build import build_index
from .query import QueryResult, ResultRow, query

__all__ = ["build_index", "query", "QueryResult", "ResultRow"]
