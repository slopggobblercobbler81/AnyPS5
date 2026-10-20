"""Command line interface for commit-msg-guard."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from commit_msg_guard import __version__
from commit_msg_guard.config import Config, DEFAULT_TYPES, TYPE_DESCRIPTIONS
from commit_msg_guard.hook import install_hook, uninstall_hook
from commit_msg_guard.reporter import Reporter, Colors
from commit_msg_guard.validator import Validator


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands and flags."""
    parser = argparse.ArgumentParser(
        prog="commit-msg-guard",
        description="Production-grade Conventional Commits validator and git hook utility.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 'check' subcommand
    check_parser = subparsers.add_parser(
        "check", help="Validate a commit message from a file, string, or stdin."
    )
    check_parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to commit message file (e.g., .git/COMMIT_EDITMSG).",
    )
    check_parser.add_argument(
        "-m", "--message", help="Commit message string to validate directly."
    )
    check_parser.add_argument(
        "-c", "--config", help="Path to custom configuration file."
    )
    check_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    check_parser.add_argument(
        "--no-color", action="store_true", help="Disable colored terminal output."
    )
    check_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress non-error messages."
    )
    check_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose details."
    )
    check_parser.add_argument(
        "--strict", action="store_true", help="Treat all warnings as errors."
    )

    # 'install' subcommand
    install_parser = subparsers.add_parser(
        "install", help="Install git hook into local repository."
    )
    install_parser.add_argument(
        "--hook-type",
        choices=["commit-msg"],
        default="commit-msg",
        help="Hook type to install (default: commit-msg).",
    )
    install_parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing hook."
    )
    install_parser.add_argument(
        "--dir", help="Path to git repository root (default: current directory)."
    )

    # 'uninstall' subcommand
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall git hook from local repository."
    )
    uninstall_parser.add_argument(
        "--hook-type",
        choices=["commit-msg"],
        default="commit-msg",
        help="Hook type to uninstall (default: commit-msg).",
    )
    uninstall_parser.add_argument(
        "--dir", help="Path to git repository root (default: current directory)."
    )

    # 'init' subcommand
    init_parser = subparsers.add_parser(
        "init", help="Create a default .commit-msg-guard.json configuration file."
    )
    init_parser.add_argument(
        "--path",
        default=".commit-msg-guard.json",
        help="Target config file path (default: .commit-msg-guard.json).",
    )
    init_parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite if file already exists."
    )

    # 'types' subcommand
    subparsers.add_parser(
        "types", help="Display standard Conventional Commit types and definitions."
    )

    return parser


def handle_check(args: argparse.Namespace) -> int:
    """Execute check command logic and return exit code."""
    raw_message: Optional[str] = None

    if args.message is not None:
        raw_message = args.message
    elif args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[commit-msg-guard] Error: File not found: {args.file}", file=sys.stderr)
            return 2
        try:
            raw_message = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[commit-msg-guard] Error reading file {args.file}: {e}", file=sys.stderr)
            return 2
    elif not sys.stdin.isatty():
        # Read from piped stdin
        raw_message = sys.stdin.read()
    else:
        # Default fallback to .git/COMMIT_EDITMSG if present
        default_file = Path(".git/COMMIT_EDITMSG")
        if default_file.exists():
            try:
                raw_message = default_file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[commit-msg-guard] Error reading {default_file}: {e}", file=sys.stderr)
                return 2
        else:
            print(
                "[commit-msg-guard] Error: No commit message supplied. "
                "Use -m 'msg', specify a file path, or pipe to stdin.",
                file=sys.stderr,
            )
            return 2

    # Load config
    if args.config:
        try:
            cfg = Config.load_from_file(args.config)
        except Exception as e:
            print(f"[commit-msg-guard] Config Error: {e}", file=sys.stderr)
            return 2
    else:
        cfg = Config.find_and_load()

    if getattr(args, "strict", False):
        cfg.warnings_as_errors = True

    # Validate
    validator = Validator(cfg)
    result = validator.validate(raw_message)

    # Report
    use_color = False if getattr(args, "no_color", False) else None
    reporter = Reporter(
        color=use_color,
        quiet=getattr(args, "quiet", False),
        verbose=getattr(args, "verbose", False),
    )

    if getattr(args, "format", "text") == "json":
        print(reporter.report_json(result))
    else:
        output = reporter.report_text(result)
        if output:
            target_stream = sys.stderr if not result.is_valid else sys.stdout
            print(output, file=target_stream)

    return 0 if result.is_valid else 1


def handle_install(args: argparse.Namespace) -> int:
    """Execute install command."""
    success, msg = install_hook(
        hook_type=args.hook_type,
        target_dir=args.dir,
        force=args.force,
    )
    if success:
        print(f"[commit-msg-guard] ✓ {msg}")
        return 0
    else:
        print(f"[commit-msg-guard] ✗ {msg}", file=sys.stderr)
        return 1


def handle_uninstall(args: argparse.Namespace) -> int:
    """Execute uninstall command."""
    success, msg = uninstall_hook(
        hook_type=args.hook_type,
        target_dir=args.dir,
    )
    if success:
        print(f"[commit-msg-guard] ✓ {msg}")
        return 0
    else:
        print(f"[commit-msg-guard] ✗ {msg}", file=sys.stderr)
        return 1


def handle_init(args: argparse.Namespace) -> int:
    """Generate default configuration file."""
    path = Path(args.path)
    if path.exists() and not args.force:
        print(
            f"[commit-msg-guard] File already exists at {path}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    default_cfg = Config.default()
    json_data = default_cfg.to_dict()

    try:
        path.write_text(json.dumps(json_data, indent=2) + "\n", encoding="utf-8")
        print(f"[commit-msg-guard] ✓ Initialized configuration file at {path}")
        return 0
    except Exception as e:
        print(f"[commit-msg-guard] Failed to write config file: {e}", file=sys.stderr)
        return 2


def handle_types() -> int:
    """Print available types and their descriptions."""
    print("Conventional Commit Types:")
    print("=" * 60)
    for t in DEFAULT_TYPES:
        desc = TYPE_DESCRIPTIONS.get(t, "")
        print(f"  • {t:<10} : {desc}")
    print("=" * 60)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    args_list = sys.argv[1:] if argv is None else argv

    # Ergonomic shortcut: If first arg is not a known subcommand and doesn't start with -
    # e.g.: `commit-msg-guard .git/COMMIT_EDITMSG` or `commit-msg-guard -m "feat: hello"`
    subcommands = {"check", "install", "uninstall", "init", "types"}
    if args_list and args_list[0] not in subcommands and not args_list[0] in ("-h", "--help", "--version"):
        # Prepend 'check' so it behaves like `commit-msg-guard check ...`
        args_list = ["check"] + args_list

    parser = build_parser()
    args = parser.parse_args(args_list)

    if not args.subcommand:
        # If no arguments provided at all, show help
        parser.print_help()
        return 0

    if args.subcommand == "check":
        return handle_check(args)
    elif args.subcommand == "install":
        return handle_install(args)
    elif args.subcommand == "uninstall":
        return handle_uninstall(args)
    elif args.subcommand == "init":
        return handle_init(args)
    elif args.subcommand == "types":
        return handle_types()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
