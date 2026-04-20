"""Tests for embed.py per bead sv-z7c and ADR-005 validation."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from scripvec_retrieval.config import EmbedConfig
from scripvec_retrieval.embed import (
    _estimate_token_count,
    _l2_normalize,
    _post_embedding,
    embed,
)


class TestEstimateTokenCount:
    """Test token count estimation."""

    def test_empty_string(self) -> None:
        assert _estimate_token_count("") == 0

    def test_short_text(self) -> None:
        result = _estimate_token_count("hello world")
        assert result == (11 // 3) + 2  # char/3 + word_count

    def test_longer_text(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        char_estimate = len(text) // 3
        word_count = 9
        assert _estimate_token_count(text) == char_estimate + word_count


class TestL2Normalize:
    """Test L2 normalization."""

    def test_unit_vector(self) -> None:
        vec = [1.0, 0.0, 0.0]
        result = _l2_normalize(vec)
        assert result == [1.0, 0.0, 0.0]

    def test_non_unit_vector(self) -> None:
        vec = [3.0, 4.0]
        result = _l2_normalize(vec)
        assert abs(result[0] - 0.6) < 1e-9
        assert abs(result[1] - 0.8) < 1e-9
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 1e-9

    def test_zero_vector_raises(self) -> None:
        with pytest.raises(RuntimeError, match="zero vector"):
            _l2_normalize([0.0, 0.0, 0.0])


class TestPostEmbedding:
    """Test raw POST functionality."""

    def test_success(self) -> None:
        cfg = EmbedConfig(
            base_url="https://test.example.com/v1",
            api_key="test-key",
            model="test-model",
            dim=3,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [1.0, 2.0, 3.0]}]}

        with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
            result = _post_embedding(cfg, "test text")

        assert result == [1.0, 2.0, 3.0]

    def test_non_2xx_raises_with_status(self) -> None:
        cfg = EmbedConfig(
            base_url="https://test.example.com/v1",
            api_key="test-key",
            model="test-model",
            dim=3,
        )
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="status 500"):
                _post_embedding(cfg, "test text")

    def test_malformed_response_raises(self) -> None:
        cfg = EmbedConfig(
            base_url="https://test.example.com/v1",
            api_key="test-key",
            model="test-model",
            dim=3,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"wrong": "structure"}

        with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Malformed"):
                _post_embedding(cfg, "test text")


class TestEmbed:
    """Test main embed function per ADR-005 validation."""

    @pytest.fixture
    def mock_config(self) -> EmbedConfig:
        return EmbedConfig(
            base_url="https://test.example.com/v1",
            api_key="test-key",
            model="test-model",
            dim=3,
        )

    def test_oversized_input_raises_without_http_call(self, mock_config: EmbedConfig) -> None:
        huge_text = "word " * 10000
        http_mock = MagicMock()

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", http_mock):
                with pytest.raises(RuntimeError, match="exceeds.*token limit"):
                    embed(huge_text)

        http_mock.assert_not_called()

    def test_wrong_length_response_raises_with_dims(self, mock_config: EmbedConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [1.0, 2.0]}]}

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
                with pytest.raises(RuntimeError, match="expected 3.*got 2"):
                    embed("test text")

    def test_non_2xx_raises_with_status_in_message(self, mock_config: EmbedConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
                with pytest.raises(RuntimeError, match="status 429"):
                    embed("test text")

    def test_normalized_vector_returned_on_success(self, mock_config: EmbedConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [3.0, 4.0, 0.0]}]}

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
                result = embed("test text")

        assert abs(result[0] - 0.6) < 1e-9
        assert abs(result[1] - 0.8) < 1e-9
        assert result[2] == 0.0
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 1e-9

    def test_verse_chunk_records_telemetry(self, mock_config: EmbedConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

        telemetry_mock = MagicMock()

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
                with patch("scripvec_retrieval.embed.EmbedTelemetry", return_value=telemetry_mock):
                    embed("test text", _verse_chunk=True)

        telemetry_mock.record.assert_called_once()

    def test_non_verse_chunk_skips_telemetry(self, mock_config: EmbedConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

        telemetry_mock = MagicMock()

        with patch("scripvec_retrieval.embed.load_embed_config", return_value=mock_config):
            with patch("scripvec_retrieval.embed.httpx.post", return_value=mock_response):
                with patch("scripvec_retrieval.embed.EmbedTelemetry", telemetry_mock):
                    embed("test text", _verse_chunk=False)

        telemetry_mock.assert_not_called()
