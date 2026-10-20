"""Tests for git hook installation and removal."""

from pathlib import Path
import pytest
from commit_msg_guard.hook import install_hook, uninstall_hook, HOOK_HEADER


def test_install_and_uninstall_hook(tmp_path: Path):
    # Simulate git repo by creating .git
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Install hook
    success, msg = install_hook(hook_type="commit-msg", target_dir=str(tmp_path))
    assert success
    hook_file = git_dir / "hooks" / "commit-msg"
    assert hook_file.exists()
    assert HOOK_HEADER in hook_file.read_text(encoding="utf-8")

    # Install again without force (should be idempotent)
    success2, msg2 = install_hook(hook_type="commit-msg", target_dir=str(tmp_path))
    assert success2
    assert "already installed" in msg2

    # Uninstall hook
    u_success, u_msg = uninstall_hook(hook_type="commit-msg", target_dir=str(tmp_path))
    assert u_success
    assert not hook_file.exists()


def test_install_with_existing_foreign_hook(tmp_path: Path):
    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    hook_file = hooks_dir / "commit-msg"
    hook_file.write_text("#!/bin/sh\n# custom pre-existing hook\necho 'custom'\n", encoding="utf-8")

    # Install should backup existing hook
    success, msg = install_hook(hook_type="commit-msg", target_dir=str(tmp_path))
    assert success
    assert "backed up" in msg

    backup_file = hooks_dir / "commit-msg.backup"
    assert backup_file.exists()
    assert "custom pre-existing hook" in backup_file.read_text(encoding="utf-8")

    # Uninstall should restore backup
    u_success, u_msg = uninstall_hook(hook_type="commit-msg", target_dir=str(tmp_path))
    assert u_success
    assert "Restored original hook" in u_msg
    assert hook_file.exists()
    assert "custom pre-existing hook" in hook_file.read_text(encoding="utf-8")


def test_install_outside_git_repo(tmp_path: Path):
    non_git_dir = tmp_path / "not_git"
    non_git_dir.mkdir()
    success, msg = install_hook(target_dir=str(non_git_dir))
    assert not success
    assert "Not inside a git repository" in msg
