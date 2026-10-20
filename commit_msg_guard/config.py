"""Configuration loader and schema for commit-msg-guard."""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

DEFAULT_TYPES = [
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
]

TYPE_DESCRIPTIONS = {
    "feat": "A new feature for the user or system",
    "fix": "A bug fix",
    "docs": "Documentation only changes",
    "style": "Changes that do not affect the meaning of the code (white-space, formatting, etc)",
    "refactor": "A code change that neither fixes a bug nor adds a feature",
    "perf": "A code change that improves performance",
    "test": "Adding missing tests or correcting existing tests",
    "build": "Changes that affect the build system or external dependencies",
    "ci": "Changes to CI configuration files and scripts",
    "chore": "Other changes that don't modify src or test files",
    "revert": "Reverts a previous commit",
}


@dataclass
class Config:
    """Configuration settings for commit message validation."""
    types: List[str] = field(default_factory=lambda: list(DEFAULT_TYPES))
    require_scope: bool = False
    allowed_scopes: Optional[List[str]] = None
    disallowed_scopes: List[str] = field(default_factory=list)
    scope_pattern: Optional[str] = r"^[a-zA-Z0-9_\-\./]+$"
    max_header_length: int = 72
    min_header_length: int = 10
    max_body_line_length: int = 100
    subject_case: str = "any"  # "lower", "sentence", "any"
    allow_trailing_period: bool = False
    require_body: bool = False
    allow_empty_body: bool = True
    ignore_merge_commits: bool = True
    ignore_revert_commits: bool = True
    ignore_patterns: List[str] = field(default_factory=lambda: [
        r"^Merge (?:branch|pull request|remote-tracking).*",
        r"^Revert \".*\"",
        r"^v?\d+\.\d+\.\d+(?:-[\w\.-]+)?$",
    ])
    strip_comments: bool = True
    comment_char: str = "#"
    warnings_as_errors: bool = False

    @classmethod
    def default(cls) -> "Config":
        return cls()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Instantiate Config from dictionary with normalization."""
        cfg = cls()
        if not data:
            return cfg

        if "types" in data and isinstance(data["types"], list):
            cfg.types = [str(t).strip() for t in data["types"] if str(t).strip()]
        if "require_scope" in data:
            cfg.require_scope = bool(data["require_scope"])
        if "allowed_scopes" in data:
            val = data["allowed_scopes"]
            if isinstance(val, list):
                cfg.allowed_scopes = [str(s).strip() for s in val]
            elif val is None:
                cfg.allowed_scopes = None
        if "disallowed_scopes" in data and isinstance(data["disallowed_scopes"], list):
            cfg.disallowed_scopes = [str(s).strip() for s in data["disallowed_scopes"]]
        if "scope_pattern" in data:
            cfg.scope_pattern = str(data["scope_pattern"]) if data["scope_pattern"] is not None else None
        if "max_header_length" in data:
            cfg.max_header_length = int(data["max_header_length"])
        if "min_header_length" in data:
            cfg.min_header_length = int(data["min_header_length"])
        if "max_body_line_length" in data:
            cfg.max_body_line_length = int(data["max_body_line_length"])
        if "subject_case" in data:
            case_val = str(data["subject_case"]).lower()
            if case_val in ("lower", "sentence", "any"):
                cfg.subject_case = case_val
        if "allow_trailing_period" in data:
            cfg.allow_trailing_period = bool(data["allow_trailing_period"])
        if "require_body" in data:
            cfg.require_body = bool(data["require_body"])
        if "allow_empty_body" in data:
            cfg.allow_empty_body = bool(data["allow_empty_body"])
        if "ignore_merge_commits" in data:
            cfg.ignore_merge_commits = bool(data["ignore_merge_commits"])
        if "ignore_revert_commits" in data:
            cfg.ignore_revert_commits = bool(data["ignore_revert_commits"])
        if "ignore_patterns" in data and isinstance(data["ignore_patterns"], list):
            cfg.ignore_patterns = [str(p) for p in data["ignore_patterns"]]
        if "strip_comments" in data:
            cfg.strip_comments = bool(data["strip_comments"])
        if "comment_char" in data:
            cfg.comment_char = str(data["comment_char"])
        if "warnings_as_errors" in data:
            cfg.warnings_as_errors = bool(data["warnings_as_errors"])

        return cfg

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to serializable dictionary."""
        return asdict(self)

    @classmethod
    def load_from_file(cls, file_path: str) -> "Config":
        """Load configuration from a specified file."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        suffix = path.suffix.lower()
        content = path.read_text(encoding="utf-8")

        if suffix in (".json", ""):
            data = json.loads(content)
            return cls.from_dict(data)
        elif suffix == ".toml":
            data = _parse_toml_section(content, "tool.commit-msg-guard")
            return cls.from_dict(data)
        else:
            # Attempt json parse
            try:
                data = json.loads(content)
                return cls.from_dict(data)
            except Exception:
                raise ValueError(f"Unsupported configuration file format: {file_path}")

    @classmethod
    def find_and_load(cls, start_dir: Optional[str] = None) -> "Config":
        """Search for configuration file from current directory upwards."""
        cur = Path(start_dir or os.getcwd()).resolve()
        search_files = [
            ".commit-msg-guard.json",
            "commit-msg-guard.json",
            ".commitlintrc.json",
            "pyproject.toml",
        ]

        # Stop at root or git root
        while True:
            for fname in search_files:
                candidate = cur / fname
                if candidate.is_file():
                    try:
                        if fname == "pyproject.toml":
                            content = candidate.read_text(encoding="utf-8")
                            parsed = _parse_toml_section(content, "tool.commit-msg-guard")
                            if parsed:
                                return cls.from_dict(parsed)
                        else:
                            return cls.load_from_file(str(candidate))
                    except Exception:
                        continue

            parent = cur.parent
            if parent == cur:
                break
            cur = parent

        return cls.default()


def _parse_toml_section(toml_text: str, target_section: str) -> Dict[str, Any]:
    """Lightweight pure-python parser for a specific TOML section without external dependencies."""
    # If tomllib or tomli is available, use it
    try:
        import tomllib  # Python 3.11+
        data = tomllib.loads(toml_text)
        keys = target_section.split(".")
        sub = data
        for k in keys:
            if isinstance(sub, dict) and k in sub:
                sub = sub[k]
            else:
                return {}
        return sub if isinstance(sub, dict) else {}
    except ImportError:
        pass

    try:
        import tomli
        data = tomli.loads(toml_text)
        keys = target_section.split(".")
        sub = data
        for k in keys:
            if isinstance(sub, dict) and k in sub:
                sub = sub[k]
            else:
                return {}
        return sub if isinstance(sub, dict) else {}
    except ImportError:
        pass

    # Basic regex scanner for [tool.commit-msg-guard]
    lines = toml_text.splitlines()
    in_section = False
    result: Dict[str, Any] = {}
    target_header = f"[{target_section}]"

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            if stripped == target_header:
                in_section = True
            else:
                in_section = False
            continue

        if in_section and "=" in stripped:
            k, v = stripped.split("=", 1)
            key = k.strip()
            val_str = v.split("#")[0].strip()

            # Simple type conversions
            if val_str.lower() in ("true", "false"):
                result[key] = (val_str.lower() == "true")
            elif val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
                result[key] = int(val_str)
            elif val_str.startswith('"') and val_str.endswith('"'):
                result[key] = val_str[1:-1]
            elif val_str.startswith("'") and val_str.endswith("'"):
                result[key] = val_str[1:-1]
            elif val_str.startswith("[") and val_str.endswith("]"):
                items_str = val_str[1:-1].strip()
                if not items_str:
                    result[key] = []
                else:
                    items = [
                        re.sub(r"^['\"]|['\"]$", "", item.strip())
                        for item in items_str.split(",")
                        if item.strip()
                    ]
                    result[key] = items

    return result
