"""Tests for command-line interface invocation and exit codes."""

import io
import json
import sys
from pathlib import Path
import pytest
from commit_msg_guard.cli import main


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "commit-msg-guard 1.0.0" in captured.out


def test_cli_types(capsys):
    ret = main(["types"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "feat" in captured.out
    assert "fix" in captured.out
    assert "docs" in captured.out


def test_cli_check_valid_message(capsys):
    ret = main(["check", "-m", "feat(auth): add google sso login"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "validation passed" in captured.out


def test_cli_check_invalid_message(capsys):
    ret = main(["check", "-m", "invalid commit message with no format", "--no-color"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Validation Failed" in captured.err


def test_cli_check_json_format(capsys):
    ret = main(["check", "-m", "feat: implement feature", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_valid"] is True
    assert data["commit"]["type"] == "feat"


def test_cli_check_file(tmp_path: Path, capsys):
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("fix: resolve race condition in worker pool\n", encoding="utf-8")

    ret = main(["check", str(msg_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "validation passed" in captured.out


def test_cli_direct_shortcut(tmp_path: Path, capsys):
    # Direct shortcut: commit-msg-guard <file> without 'check' subcommand
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("fix: resolve race condition in worker pool\n", encoding="utf-8")

    ret = main([str(msg_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "validation passed" in captured.out


def test_cli_stdin_input(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("feat(cli): accept stdin commit messages\n"))
    # Also simulate isatty() returning False
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    ret = main(["check"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "validation passed" in captured.out


def test_cli_init(tmp_path: Path, capsys):
    cfg_file = tmp_path / "custom-config.json"
    ret = main(["init", "--path", str(cfg_file)])
    assert ret == 0
    assert cfg_file.exists()
    content = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "types" in content


def test_cli_install_and_uninstall(tmp_path: Path, capsys):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Install
    ret_install = main(["install", "--dir", str(tmp_path)])
    assert ret_install == 0
    hook_file = git_dir / "hooks" / "commit-msg"
    assert hook_file.exists()

    # Uninstall
    ret_uninstall = main(["uninstall", "--dir", str(tmp_path)])
    assert ret_uninstall == 0
    assert not hook_file.exists()
