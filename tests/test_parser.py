"""Tests for Conventional Commits parser."""

import pytest
from commit_msg_guard.parser import CommitParser


def test_parse_simple_commit():
    parser = CommitParser()
    msg = "feat: add user login endpoint"
    commit = parser.parse(msg)

    assert commit.header == "feat: add user login endpoint"
    assert commit.type == "feat"
    assert commit.scope is None
    assert commit.is_breaking is False
    assert commit.description == "add user login endpoint"
    assert commit.body is None
    assert commit.footers == []


def test_parse_with_scope():
    parser = CommitParser()
    msg = "fix(auth): resolve session timeout bug"
    commit = parser.parse(msg)

    assert commit.header == "fix(auth): resolve session timeout bug"
    assert commit.type == "fix"
    assert commit.scope == "auth"
    assert commit.is_breaking is False
    assert commit.description == "resolve session timeout bug"


def test_parse_breaking_indicator():
    parser = CommitParser()
    msg = "refactor(api)!: redesign authentication endpoints"
    commit = parser.parse(msg)

    assert commit.type == "refactor"
    assert commit.scope == "api"
    assert commit.is_breaking is True
    assert commit.description == "redesign authentication endpoints"


def test_parse_multiline_body_and_footer():
    raw = """feat(search): implement full-text search engine

This engine uses inverted index for fast keyword matching.
It handles stemming and tokenization gracefully.

Reviewed-by: Alice <alice@example.com>
Refs: #42, #43
"""
    parser = CommitParser()
    commit = parser.parse(raw)

    assert commit.type == "feat"
    assert commit.scope == "search"
    assert commit.description == "implement full-text search engine"
    assert "uses inverted index" in commit.body
    assert len(commit.footers) == 2
    assert commit.footers[0] == ("Reviewed-by", "Alice <alice@example.com>")
    assert commit.footers[1] == ("Refs", "#42, #43")


def test_parse_breaking_change_in_footer():
    raw = """perf: optimize database query throughput

BREAKING CHANGE: changes query API signature from get(id) to get(id, options)
"""
    parser = CommitParser()
    commit = parser.parse(raw)

    assert commit.type == "perf"
    assert commit.is_breaking is True
    assert len(commit.footers) == 1
    assert commit.footers[0][0] == "BREAKING CHANGE"
    assert "query API signature" in commit.footers[0][1]


def test_parse_strip_git_comments():
    raw = """fix: fix null pointer exception
# Please enter the commit message for your changes. Lines starting
# with '#' will be ignored, and an empty message aborts the commit.
#
# On branch main
"""
    parser = CommitParser(strip_comments=True, comment_char="#")
    commit = parser.parse(raw)

    assert commit.header == "fix: fix null pointer exception"
    assert commit.type == "fix"
    assert commit.description == "fix null pointer exception"
    assert commit.clean_message == "fix: fix null pointer exception"


def test_parse_empty_message():
    parser = CommitParser()
    commit = parser.parse("")
    assert commit.clean_message == ""
    assert commit.header == ""
    assert commit.type is None
