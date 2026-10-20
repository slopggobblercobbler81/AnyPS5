"""Tests for configuration parsing, serializing, and file discovery."""

import json
from pathlib import Path
import pytest
from commit_msg_guard.config import Config, _parse_toml_section


def test_default_config():
    cfg = Config.default()
    assert "feat" in cfg.types
    assert "fix" in cfg.types
    assert cfg.max_header_length == 72
    assert cfg.min_header_length == 10
    assert cfg.allow_trailing_period is False
    assert cfg.require_scope is False


def test_config_from_dict():
    data = {
        "types": ["feat", "fix", "custom"],
        "require_scope": True,
        "allowed_scopes": ["api", "ui"],
        "max_header_length": 80,
        "subject_case": "lower",
        "allow_trailing_period": True,
    }
    cfg = Config.from_dict(data)
    assert cfg.types == ["feat", "fix", "custom"]
    assert cfg.require_scope is True
    assert cfg.allowed_scopes == ["api", "ui"]
    assert cfg.max_header_length == 80
    assert cfg.subject_case == "lower"
    assert cfg.allow_trailing_period is True


def test_config_load_from_json(tmp_path: Path):
    cfg_file = tmp_path / ".commit-msg-guard.json"
    data = {
        "types": ["feat", "fix"],
        "max_header_length": 90,
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    cfg = Config.load_from_file(str(cfg_file))
    assert cfg.types == ["feat", "fix"]
    assert cfg.max_header_length == 90


def test_config_load_from_toml(tmp_path: Path):
    toml_file = tmp_path / "pyproject.toml"
    toml_content = """
[build-system]
requires = ["setuptools"]

[tool.commit-msg-guard]
types = ["feat", "fix", "chore"]
max_header_length = 65
require_scope = true
allow_trailing_period = false
"""
    toml_file.write_text(toml_content, encoding="utf-8")

    cfg = Config.load_from_file(str(toml_file))
    assert cfg.types == ["feat", "fix", "chore"]
    assert cfg.max_header_length == 65
    assert cfg.require_scope is True
    assert cfg.allow_trailing_period is False


def test_find_and_load_discovery(tmp_path: Path):
    sub_dir = tmp_path / "subdir" / "nested"
    sub_dir.mkdir(parents=True)

    cfg_file = tmp_path / "commit-msg-guard.json"
    cfg_file.write_text(json.dumps({"max_header_length": 110}), encoding="utf-8")

    cfg = Config.find_and_load(start_dir=str(sub_dir))
    assert cfg.max_header_length == 110
