"""Tests for query.py drift check and result handling."""

import os
from unittest.mock import patch

import pytest

from scripvec_retrieval.query import _drift_check_endpoint


class TestDriftCheckEndpoint:
    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_matching_config_passes(self) -> None:
        """Matching endpoint config passes."""
        _drift_check_endpoint("https://api.test.com", "test-model", 1536)

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.other.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_url_mismatch_raises(self) -> None:
        """URL mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "base_url" in msg
        assert "api.test.com" in msg
        assert "api.other.com" in msg

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "other-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_model_mismatch_raises(self) -> None:
        """Model mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "model" in msg
        assert "test-model" in msg
        assert "other-model" in msg

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "768",
    })
    def test_dim_mismatch_raises(self) -> None:
        """Dimension mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "dim" in msg
        assert "1536" in msg
        assert "768" in msg
