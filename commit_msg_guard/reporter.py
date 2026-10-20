"""Terminal and structured reporter for validation results."""

import json
import os
import sys
from typing import Optional
from commit_msg_guard.models import ValidationResult, ValidationError


class Colors:
    """ANSI color codes with terminal detection and NO_COLOR support."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


def supports_color() -> bool:
    """Determine whether current output stream supports ANSI colors."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


class Reporter:
    """Formats and prints validation results to stdout/stderr."""

    def __init__(self, color: Optional[bool] = None, quiet: bool = False, verbose: bool = False):
        if color is None:
            self.use_color = supports_color()
        else:
            self.use_color = color
        self.quiet = quiet
        self.verbose = verbose

    def _c(self, text: str, code: str) -> str:
        """Apply color code if enabled."""
        if not self.use_color:
            return text
        return f"{code}{text}{Colors.RESET}"

    def report_text(self, result: ValidationResult) -> str:
        """Generate human-readable text report."""
        lines = []

        if result.ignored:
            lines.append(
                self._c(f"ℹ Ignored commit: {result.ignore_reason or 'Matches ignore rule'}", Colors.CYAN)
            )
            return "\n".join(lines)

        if result.is_valid and not result.has_warnings:
            if not self.quiet:
                lines.append(self._c("✓ Conventional Commit validation passed!", Colors.GREEN + Colors.BOLD))
                if self.verbose and result.commit:
                    lines.append(self._format_commit_details(result))
            return "\n".join(lines)

        # There are errors or warnings
        header = result.commit.header if result.commit else ""
        if header:
            lines.append(self._c("Commit Header:", Colors.BOLD))
            lines.append(f"  {self._c(header, Colors.WHITE)}")
            lines.append("")

        if result.errors:
            lines.append(self._c(f"✗ Conventional Commit Validation Failed ({len(result.errors)} error{'s' if len(result.errors) > 1 else ''}):", Colors.RED + Colors.BOLD))
            for err in result.errors:
                lines.extend(self._format_issue(err, is_error=True))

        if result.warnings:
            lines.append(self._c(f"⚠ Warnings ({len(result.warnings)}):", Colors.YELLOW + Colors.BOLD))
            for warn in result.warnings:
                lines.extend(self._format_issue(warn, is_error=False))

        lines.append("")
        lines.append(self._format_help_tip())

        return "\n".join(lines)

    def _format_issue(self, issue: ValidationError, is_error: bool) -> list:
        tag_color = Colors.RED if is_error else Colors.YELLOW
        tag_text = "ERROR" if is_error else "WARN"
        lines = []

        loc = f"Line {issue.line_number}" if issue.line_number else ""
        if issue.column_number and loc:
            loc += f", Col {issue.column_number}"
        loc_str = f" [{loc}]" if loc else ""

        lines.append(
            f"  {self._c(f'[{tag_text}]', tag_color + Colors.BOLD)} "
            f"{self._c(issue.code, Colors.BOLD)}{loc_str}: {issue.message}"
        )
        if issue.suggestion:
            lines.append(
                f"          {self._c('Suggestion:', Colors.CYAN)} {self._c(issue.suggestion, Colors.GREEN)}"
            )

        return lines

    def _format_commit_details(self, result: ValidationResult) -> str:
        c = result.commit
        if not c:
            return ""
        details = [
            self._c("Parsed Details:", Colors.CYAN),
            f"  • Type: {c.type}",
            f"  • Scope: {c.scope or '(none)'}",
            f"  • Breaking: {'YES' if c.is_breaking else 'no'}",
            f"  • Description: {c.description}",
        ]
        if c.footers:
            details.append(f"  • Footers ({len(c.footers)}):")
            for t, val in c.footers:
                details.append(f"      - {t}: {val}")
        return "\n".join(details)

    def _format_help_tip(self) -> str:
        return (
            self._c("Conventional Commits format reminder:", Colors.DIM) + "\n"
            + self._c("  <type>[optional scope][!]: <description>\n\n  [optional body]\n\n  [optional footer(s)]", Colors.DIM)
        )

    def report_json(self, result: ValidationResult) -> str:
        """Generate JSON report string."""
        return json.dumps(result.to_dict(), indent=2)
