# commit-msg-guard

[![CI](https://github.com/slopggobblercobbler81/commit-msg-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/commit-msg-guard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](pyproject.toml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)

**`commit-msg-guard`** is a production-grade, zero-dependency CLI utility and Git hook to strictly validate git commit messages against the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification.

---

## Key Features

- **Standard Compliance**: Full implementation of Conventional Commits v1.0.0 specification (`<type>(<scope>): <description>`).
- **Zero External Dependencies**: Pure Python standard library implementation; lightweight and lightning fast.
- **Intelligent Diagnostics**: Pinpoints errors, suggests corrections (Levenshtein distance & alias matching, e.g. `feature:` $\rightarrow$ `feat:`).
- **Native Git Hook Integration**: One-command installation for `.git/hooks/commit-msg` with non-destructive backups.
- **Pre-commit Support**: Drop-in `.pre-commit-hooks.yaml` support for `pre-commit` framework users.
- **Flexible Configuration**: JSON (`.commit-msg-guard.json`) or TOML (`pyproject.toml` under `[tool.commit-msg-guard]`).
- **Developer-Friendly Output**: Rich terminal colors, line pointers, and machine-readable JSON (`--format json`).
- **High Compatibility**: Tested across Python 3.8, 3.9, 3.10, 3.11, and 3.12 on Linux, macOS, and Windows.

---

## Installation

### Via Pip

```bash
pip install commit-msg-guard
```

### Via Pipx (Recommended for global CLI usage)

```bash
pipx install commit-msg-guard
```

### From Source (Local Development)

```bash
git clone https://github.com/slopggobblercobbler81/commit-msg-guard.git
cd commit-msg-guard
pip install -e .
```

---

## Quickstart

### 1. Validate a commit message string

```bash
commit-msg-guard check -m "feat(auth): support OAuth2 PKCE flow"
```

Output:
```
✓ Conventional Commit validation passed!
```

### 2. Validate commit message file (e.g. from git hook)

```bash
commit-msg-guard check .git/COMMIT_EDITMSG
```

Or using the ergonomic shortcut:

```bash
commit-msg-guard .git/COMMIT_EDITMSG
```

### 3. Install Git Hook

In your repository root, run:

```bash
commit-msg-guard install
```

This installs `.git/hooks/commit-msg` and makes it executable. Any subsequent `git commit` will automatically be validated before being finalized.

To uninstall:
```bash
commit-msg-guard uninstall
```

---

## Using with `pre-commit`

Add this entry to your repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/slopggobblercobbler81/commit-msg-guard
    rev: v1.0.0
    hooks:
      - id: commit-msg-guard
        stages: [commit-msg]
```

---

## CLI Reference

```
usage: commit-msg-guard [-h] [--version] {check,install,uninstall,init,types} ...
```

### Subcommands

| Subcommand | Description |
| :--- | :--- |
| `check [file] [-m msg]` | Validate a commit message from a file, direct string, or stdin. |
| `install [--force] [--dir DIR]` | Install the `.git/hooks/commit-msg` hook. |
| `uninstall [--dir DIR]` | Remove the installed git hook and restore previous hook backup. |
| `init [--path PATH] [--force]` | Generate a default `.commit-msg-guard.json` configuration file. |
| `types` | List standard Conventional Commit types and definitions. |

### Validation Flags (`check`)

- `-m, --message TEXT`: Raw commit message to validate.
- `-c, --config FILE`: Path to custom configuration file.
- `--format {text,json}`: Formatter for results (default: `text`).
- `--no-color`: Disable ANSI color output.
- `-q, --quiet`: Suppress passing messages, output only errors.
- `-v, --verbose`: Display detailed parsed commit breakdown.
- `--strict`: Treat warnings as fatal errors (exit code 1).

---

## Configuration

Initialize a default configuration:

```bash
commit-msg-guard init
```

Generates `.commit-msg-guard.json`:

```json
{
  "types": [
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
    "revert"
  ],
  "require_scope": false,
  "allowed_scopes": null,
  "disallowed_scopes": [],
  "scope_pattern": "^[a-zA-Z0-9_\\-\\./]+$",
  "max_header_length": 72,
  "min_header_length": 10,
  "max_body_line_length": 100,
  "subject_case": "any",
  "allow_trailing_period": false,
  "require_body": false,
  "allow_empty_body": true,
  "ignore_merge_commits": true,
  "ignore_revert_commits": true,
  "ignore_patterns": [
    "^Merge (?:branch|pull request|remote-tracking).*",
    "^Revert \".*\"",
    "^v?\\d+\\.\\d+\\.\\d+(?:-[\\w\\.-]+)?$"
  ],
  "strip_comments": true,
  "comment_char": "#",
  "warnings_as_errors": false
}
```

### Configuration in `pyproject.toml`

You can also embed the settings directly inside your project's `pyproject.toml`:

```toml
[tool.commit-msg-guard]
types = ["feat", "fix", "docs", "chore", "refactor"]
max_header_length = 72
require_scope = true
allowed_scopes = ["core", "api", "ui", "docs", "ci"]
allow_trailing_period = false
```

---

## Conventional Commits Primer

The Conventional Commits specification is a lightweight convention on top of commit messages:

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

### Standard Types

| Type | Description |
| :--- | :--- |
| `feat` | A new feature for the user or system |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Changes that do not affect the meaning of the code (formatting, etc.) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Code change that improves execution performance |
| `test` | Adding missing tests or correcting existing tests |
| `build` | Changes that affect build systems or external dependencies |
| `ci` | Changes to CI configuration files and automation scripts |
| `chore` | Routine maintenance tasks |
| `revert` | Reverts a previous commit |

### Breaking Changes

Breaking changes can be indicated in either of two ways:
1. Append an exclamation mark (`!`) before the colon in the header:
   ```
   feat(api)!: remove v1 endpoints
   ```
2. Include a footer starting with `BREAKING CHANGE:`:
   ```
   feat(api): redesign token validation

   BREAKING CHANGE: payload structure has migrated from v1 to v2 schema.
   ```

---

## Running Tests

Run the test suite locally with `pytest`:

```bash
pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
