"""Tests for Conventional Commits validator rules and error reporting."""

import pytest
from commit_msg_guard.config import Config
from commit_msg_guard.validator import Validator, validate_message, find_closest_type


def test_valid_standard_commits():
    valid_msgs = [
        "feat: add oauth2 login flow",
        "fix(core): prevent race condition in event loop",
        "docs: update installation instructions",
        "style(ui): fix button margin and padding",
        "refactor: extract parser into standalone module",
        "perf: optimize memory footprint during import",
        "test: add unit tests for validator engine",
        "build(deps): bump cryptography from 41.0 to 42.0",
        "ci: add multi-platform test matrix",
        "chore: clean up deprecated helper functions",
        "revert: revert last merge request",
        "feat(api)!: remove deprecated v1 endpoints",
    ]
    for msg in valid_msgs:
        res = validate_message(msg)
        assert res.is_valid, f"Expected valid for '{msg}', got errors: {[e.message for e in res.errors]}"
        assert len(res.errors) == 0


def test_empty_commit_message():
    res = validate_message("")
    assert not res.is_valid
    assert any(e.code == "EMPTY_COMMIT_MESSAGE" for e in res.errors)

    res_spaces = validate_message("   \n\n  \t  ")
    assert not res_spaces.is_valid
    assert any(e.code == "EMPTY_COMMIT_MESSAGE" for e in res_spaces.errors)


def test_invalid_type_and_suggestion():
    res = validate_message("feature: add exciting new capability")
    assert not res.is_valid
    err = next(e for e in res.errors if e.code == "INVALID_TYPE")
    assert "feat" in err.suggestion

    res2 = validate_message("bugfix: resolve crash on startup")
    assert not res2.is_valid
    err2 = next(e for e in res2.errors if e.code == "INVALID_TYPE")
    assert err2.suggestion == "fix"


def test_missing_space_after_colon():
    res = validate_message("feat:add missing parameter")
    assert not res.is_valid
    assert any(e.code == "MISSING_SPACE_AFTER_COLON" for e in res.errors)
    err = next(e for e in res.errors if e.code == "MISSING_SPACE_AFTER_COLON")
    assert err.suggestion == "feat: add missing parameter"


def test_missing_colon():
    res = validate_message("feat add missing parameter")
    assert not res.is_valid
    assert any(e.code == "MISSING_COLON" for e in res.errors)


def test_unexpected_whitespace_before_colon():
    res = validate_message("feat : add missing parameter")
    assert not res.is_valid
    assert any(e.code == "UNEXPECTED_WHITESPACE" for e in res.errors)


def test_scope_requirements():
    cfg = Config(require_scope=True)
    res = validate_message("feat: add parameter", cfg)
    assert not res.is_valid
    assert any(e.code == "SCOPE_REQUIRED" for e in res.errors)

    res_valid = validate_message("feat(cli): add parameter", cfg)
    assert res_valid.is_valid


def test_allowed_scopes():
    cfg = Config(allowed_scopes=["auth", "api", "db"])
    res_bad = validate_message("feat(frontend): create dark mode", cfg)
    assert not res_bad.is_valid
    assert any(e.code == "DISALLOWED_SCOPE" for e in res_bad.errors)

    res_good = validate_message("feat(auth): create dark mode", cfg)
    assert res_good.is_valid


def test_disallowed_scopes():
    cfg = Config(disallowed_scopes=["wip", "temp"])
    res = validate_message("feat(wip): work in progress feature", cfg)
    assert not res.is_valid
    assert any(e.code == "FORBIDDEN_SCOPE" for e in res.errors)


def test_scope_pattern_regex():
    cfg = Config(scope_pattern=r"^[a-z]+$")
    res_bad = validate_message("feat(AUTH_123): change header", cfg)
    assert not res_bad.is_valid
    assert any(e.code == "INVALID_SCOPE_FORMAT" for e in res_bad.errors)

    res_good = validate_message("feat(auth): change header", cfg)
    assert res_good.is_valid


def test_trailing_period_rule():
    # By default, allow_trailing_period = False
    res = validate_message("fix: fix database reconnect.")
    assert not res.is_valid
    assert any(e.code == "TRAILING_PERIOD" for e in res.errors)

    # When allowed
    cfg = Config(allow_trailing_period=True)
    res_ok = validate_message("fix: fix database reconnect.", cfg)
    assert res_ok.is_valid


def test_subject_case():
    cfg_lower = Config(subject_case="lower")
    res_bad = validate_message("feat: Add login endpoint", cfg_lower)
    assert not res_bad.is_valid
    assert any(e.code == "SUBJECT_CASE_LOWER" for e in res_bad.errors)

    res_good = validate_message("feat: add login endpoint", cfg_lower)
    assert res_good.is_valid

    cfg_sentence = Config(subject_case="sentence")
    res_sent_bad = validate_message("feat: add login endpoint", cfg_sentence)
    assert not res_sent_bad.is_valid
    assert any(e.code == "SUBJECT_CASE_SENTENCE" for e in res_sent_bad.errors)

    res_sent_good = validate_message("feat: Add login endpoint", cfg_sentence)
    assert res_sent_good.is_valid


def test_header_length_limits():
    cfg = Config(min_header_length=15, max_header_length=30)

    # Too short (< 15)
    res_short = validate_message("feat: a", cfg)
    assert not res_short.is_valid
    assert any(e.code == "MIN_HEADER_LENGTH" for e in res_short.errors)

    # Too long (> 30)
    res_long = validate_message("feat: this commit header exceeds the thirty limit completely", cfg)
    assert not res_long.is_valid
    assert any(e.code == "MAX_HEADER_LENGTH" for e in res_long.errors)

    # Just right
    res_just = validate_message("feat: valid length header", cfg)
    assert res_just.is_valid


def test_missing_blank_line_before_body():
    msg = """feat: implement cache service
This is the second line without a preceding blank line."""
    res = validate_message(msg)
    assert not res.is_valid
    assert any(e.code == "MISSING_BLANK_LINE_BEFORE_BODY" for e in res.errors)


def test_body_required():
    cfg = Config(require_body=True)
    res_no_body = validate_message("feat: add search query", cfg)
    assert not res_no_body.is_valid
    assert any(e.code == "BODY_REQUIRED" for e in res_no_body.errors)

    msg_with_body = """feat: add search query

This provides query parser and token indexing.
"""
    res_with_body = validate_message(msg_with_body, cfg)
    assert res_with_body.is_valid


def test_max_body_line_length_and_url_exemption():
    cfg = Config(max_body_line_length=50)

    # Line exceeding 50 chars that is plain text
    msg_long = "feat: add webhook integration\n\n" + ("x" * 60)
    res = validate_message(msg_long, cfg)
    assert any(w.code == "MAX_BODY_LINE_LENGTH" for w in res.warnings)

    # Exemption for URLs
    url_line = "See documentation at https://example.com/very/long/url/that/exceeds/fifty/characters/in/total"
    msg_url = f"feat: add webhook integration\n\n{url_line}"
    res_url = validate_message(msg_url, cfg)
    assert len(res_url.warnings) == 0


def test_ignore_patterns():
    # Merge commits
    res_merge = validate_message("Merge branch 'feature/oauth' into main")
    assert res_merge.is_valid
    assert res_merge.ignored is True

    res_pr = validate_message("Merge pull request #123 from user/branch")
    assert res_pr.is_valid
    assert res_pr.ignored is True

    # Revert commits
    res_revert = validate_message('Revert "feat: add experimental feature"')
    assert res_revert.is_valid
    assert res_revert.ignored is True

    # Custom version tag
    res_tag = validate_message("v1.2.3")
    assert res_tag.is_valid
    assert res_tag.ignored is True


def test_warnings_as_errors():
    cfg = Config(max_body_line_length=40, warnings_as_errors=True)
    msg = "feat: add feature\n\n" + ("a" * 50)
    res = validate_message(msg, cfg)
    assert not res.is_valid
    assert any(e.code == "MAX_BODY_LINE_LENGTH" for e in res.errors)
