"""Tests for config.py per bead sv-2a0."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from scripvec_retrieval.config import EmbedConfig, _read_optional_config_file, load_embed_config


class TestEmbedConfig:
    """Test EmbedConfig dataclass invariants."""

    def test_valid_config(self) -> None:
        cfg = EmbedConfig(
            base_url="https://example.com/v1",
            api_key="test-key",
            model="test-model",
            dim=1024,
        )
        assert cfg.base_url == "https://example.com/v1"
        assert cfg.api_key == "test-key"
        assert cfg.model == "test-model"
        assert cfg.dim == 1024

    def test_empty_base_url_raises(self) -> None:
        with pytest.raises(ValueError, match="base_url must be non-empty"):
            EmbedConfig(base_url="", api_key="key", model="model", dim=1024)

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="api_key must be non-empty"):
            EmbedConfig(base_url="url", api_key="", model="model", dim=1024)

    def test_empty_model_raises(self) -> None:
        with pytest.raises(ValueError, match="model must be non-empty"):
            EmbedConfig(base_url="url", api_key="key", model="", dim=1024)

    def test_zero_dim_raises(self) -> None:
        with pytest.raises(ValueError, match="dim must be positive"):
            EmbedConfig(base_url="url", api_key="key", model="model", dim=0)

    def test_negative_dim_raises(self) -> None:
        with pytest.raises(ValueError, match="dim must be positive"):
            EmbedConfig(base_url="url", api_key="key", model="model", dim=-1)

    def test_frozen(self) -> None:
        cfg = EmbedConfig(base_url="url", api_key="key", model="model", dim=1024)
        with pytest.raises(AttributeError):
            cfg.base_url = "new"  # type: ignore[misc]


class TestLoadEmbedConfig:
    """Test load_embed_config with env vars and config file."""

    @pytest.fixture
    def clean_env(self) -> Generator[None, None, None]:
        """Remove embed-related env vars for test isolation."""
        keys = ["OPENAI_BASE_URL", "OPENAI_API_KEY", "SCRIPVEC_EMBED_MODEL", "SCRIPVEC_EMBED_DIM"]
        old_values = {k: os.environ.pop(k, None) for k in keys}
        yield
        for k, v in old_values.items():
            if v is not None:
                os.environ[k] = v

    def test_valid_env_returns_config(self, clean_env: None) -> None:
        with patch.dict(os.environ, {
            "OPENAI_BASE_URL": "https://test.example.com/v1",
            "OPENAI_API_KEY": "test-api-key",
            "SCRIPVEC_EMBED_MODEL": "test-model-id",
            "SCRIPVEC_EMBED_DIM": "512",
        }):
            with patch("scripvec_retrieval.config._read_optional_config_file", return_value={}):
                cfg = load_embed_config()
        assert cfg.base_url == "https://test.example.com/v1"
        assert cfg.api_key == "test-api-key"
        assert cfg.model == "test-model-id"
        assert cfg.dim == 512

    def test_missing_env_raises(self, clean_env: None) -> None:
        with patch("scripvec_retrieval.config._read_optional_config_file", return_value={}):
            with pytest.raises(RuntimeError, match="Cannot resolve embedding config"):
                load_embed_config()

    def test_partial_env_missing_raises(self, clean_env: None) -> None:
        with patch.dict(os.environ, {
            "OPENAI_BASE_URL": "https://test.example.com/v1",
        }):
            with patch("scripvec_retrieval.config._read_optional_config_file", return_value={}):
                with pytest.raises(RuntimeError, match="api_key.*model.*dim"):
                    load_embed_config()

    def test_invalid_dim_raises(self, clean_env: None) -> None:
        with patch.dict(os.environ, {
            "OPENAI_BASE_URL": "https://test.example.com/v1",
            "OPENAI_API_KEY": "test-api-key",
            "SCRIPVEC_EMBED_MODEL": "test-model-id",
            "SCRIPVEC_EMBED_DIM": "not-a-number",
        }):
            with patch("scripvec_retrieval.config._read_optional_config_file", return_value={}):
                with pytest.raises(RuntimeError, match="dim must be an integer"):
                    load_embed_config()

    def test_config_file_fallback(self, clean_env: None) -> None:
        file_config = {
            "base_url": "https://file.example.com/v1",
            "api_key": "file-api-key",
            "model": "file-model",
            "dim": 768,
        }
        with patch("scripvec_retrieval.config._read_optional_config_file", return_value=file_config):
            cfg = load_embed_config()
        assert cfg.base_url == "https://file.example.com/v1"
        assert cfg.api_key == "file-api-key"
        assert cfg.model == "file-model"
        assert cfg.dim == 768

    def test_env_overrides_file(self, clean_env: None) -> None:
        file_config = {
            "base_url": "https://file.example.com/v1",
            "api_key": "file-api-key",
            "model": "file-model",
            "dim": 768,
        }
        with patch.dict(os.environ, {
            "OPENAI_BASE_URL": "https://env.example.com/v1",
        }):
            with patch("scripvec_retrieval.config._read_optional_config_file", return_value=file_config):
                cfg = load_embed_config()
        assert cfg.base_url == "https://env.example.com/v1"
        assert cfg.api_key == "file-api-key"


class TestReadOptionalConfigFile:
    """Test _read_optional_config_file behavior."""

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        with patch("scripvec_retrieval.config.Path.cwd", return_value=tmp_path):
            result = _read_optional_config_file()
        assert result == {}

    def test_valid_file_returns_dict(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".scripvec_config.json"
        config_file.write_text('{"base_url": "https://test.com", "dim": 512}')
        with patch("scripvec_retrieval.config.Path.cwd", return_value=tmp_path):
            result = _read_optional_config_file()
        assert result == {"base_url": "https://test.com", "dim": 512}

    def test_corrupt_json_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".scripvec_config.json"
        config_file.write_text("{invalid json")
        with patch("scripvec_retrieval.config.Path.cwd", return_value=tmp_path):
            with pytest.raises(RuntimeError, match="corrupt"):
                _read_optional_config_file()

    def test_non_object_json_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".scripvec_config.json"
        config_file.write_text('["array", "not", "object"]')
        with patch("scripvec_retrieval.config.Path.cwd", return_value=tmp_path):
            with pytest.raises(RuntimeError, match="must contain a JSON object"):
                _read_optional_config_file()
