"""Validation engine for Conventional Commits."""

import re
from typing import List, Optional, Tuple
from commit_msg_guard.config import Config, TYPE_DESCRIPTIONS
from commit_msg_guard.models import (
    ConventionalCommit,
    ValidationError,
    ValidationResult,
)
from commit_msg_guard.parser import CommitParser, HEADER_PATTERN

# Common aliases / misspellings mapped to conventional commit types
COMMON_TYPE_ALIASES = {
    "feature": "feat",
    "features": "feat",
    "bug": "fix",
    "bugfix": "fix",
    "fixing": "fix",
    "fixes": "fix",
    "doc": "docs",
    "documents": "docs",
    "documentation": "docs",
    "cleanup": "chore",
    "maintenance": "chore",
    "perfomance": "perf",
    "performance": "perf",
    "testing": "test",
    "tests": "test",
    "refactoring": "refactor",
    "formatting": "style",
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def find_closest_type(raw_type: str, allowed_types: List[str]) -> Optional[str]:
    """Find closest allowed type from alias dictionary or string edit distance."""
    lower = raw_type.lower()
    if lower in COMMON_TYPE_ALIASES and COMMON_TYPE_ALIASES[lower] in allowed_types:
        return COMMON_TYPE_ALIASES[lower]

    best_match: Optional[str] = None
    best_dist = 999
    for candidate in allowed_types:
        dist = levenshtein_distance(lower, candidate)
        if dist < best_dist and dist <= 3:
            best_dist = dist
            best_match = candidate
    return best_match


class Validator:
    """Conventional Commit validator against Config specification."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.default()
        self.parser = CommitParser(
            strip_comments=self.config.strip_comments,
            comment_char=self.config.comment_char,
        )

    def validate(self, message: str) -> ValidationResult:
        """Validate raw commit message and return detailed ValidationResult."""
        errors: List[ValidationError] = []
        warnings: List[ValidationError] = []

        # 1. Parse commit
        commit = self.parser.parse(message)

        # 2. Check for empty commit message
        if not commit.clean_message.strip():
            errors.append(
                ValidationError(
                    code="EMPTY_COMMIT_MESSAGE",
                    message="Commit message cannot be empty.",
                    line_number=1,
                    severity="error",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, commit=commit)

        # 3. Check ignore rules
        header = commit.header
        if self._should_ignore(header):
            return ValidationResult(
                is_valid=True,
                ignored=True,
                ignore_reason=f"Matched ignore pattern for '{header}'",
                commit=commit,
            )

        # 4. Check second line blank if multiline
        cleaned_lines = [
            line for line in commit.clean_message.splitlines()
        ]
        if len(cleaned_lines) > 1:
            second_line = cleaned_lines[1]
            if second_line.strip():
                errors.append(
                    ValidationError(
                        code="MISSING_BLANK_LINE_BEFORE_BODY",
                        message="Second line of commit message must be blank (separate header and body).",
                        line_number=2,
                        suggestion="Insert a blank line after the subject line.",
                        severity="error",
                    )
                )

        # 5. Header format validation
        match = HEADER_PATTERN.match(header)
        if not match:
            # Diagnose specific header format mistakes
            diag_err = self._diagnose_header_format(header)
            errors.append(diag_err)
        else:
            commit_type = match.group("type")
            commit_scope = match.group("scope")
            commit_desc = match.group("description")

            # 5a. Validate Type
            if commit_type not in self.config.types:
                suggestion = find_closest_type(commit_type, self.config.types)
                sugg_msg = f"Did you mean '{suggestion}'?" if suggestion else f"Allowed types: {', '.join(self.config.types)}"
                errors.append(
                    ValidationError(
                        code="INVALID_TYPE",
                        message=f"Commit type '{commit_type}' is not recognized. {sugg_msg}",
                        line_number=1,
                        column_number=1,
                        suggestion=suggestion,
                        severity="error",
                    )
                )

            # 5b. Validate Scope
            if self.config.require_scope and not commit_scope:
                errors.append(
                    ValidationError(
                        code="SCOPE_REQUIRED",
                        message="A scope is required in the commit header, e.g. 'type(scope): description'.",
                        line_number=1,
                        severity="error",
                    )
                )
            elif commit_scope:
                if self.config.allowed_scopes is not None:
                    if commit_scope not in self.config.allowed_scopes:
                        errors.append(
                            ValidationError(
                                code="DISALLOWED_SCOPE",
                                message=(
                                    f"Scope '{commit_scope}' is not in allowed scopes list: "
                                    f"{', '.join(self.config.allowed_scopes)}"
                                ),
                                line_number=1,
                                severity="error",
                            )
                        )
                if commit_scope in self.config.disallowed_scopes:
                    errors.append(
                        ValidationError(
                            code="FORBIDDEN_SCOPE",
                            message=f"Scope '{commit_scope}' is explicitly forbidden.",
                            line_number=1,
                            severity="error",
                        )
                    )
                if self.config.scope_pattern:
                    if not re.match(self.config.scope_pattern, commit_scope):
                        errors.append(
                            ValidationError(
                                code="INVALID_SCOPE_FORMAT",
                                message=(
                                    f"Scope '{commit_scope}' does not match pattern: "
                                    f"{self.config.scope_pattern}"
                                ),
                                line_number=1,
                                severity="error",
                            )
                        )

            # 5c. Validate Description
            if not commit_desc or not commit_desc.strip():
                errors.append(
                    ValidationError(
                        code="MISSING_DESCRIPTION",
                        message="Commit description cannot be empty.",
                        line_number=1,
                        severity="error",
                    )
                )
            else:
                desc_stripped = commit_desc.strip()
                # Check trailing period
                if not self.config.allow_trailing_period and desc_stripped.endswith("."):
                    errors.append(
                        ValidationError(
                            code="TRAILING_PERIOD",
                            message="Commit description should not end with a period ('.').",
                            line_number=1,
                            suggestion=desc_stripped[:-1],
                            severity="error",
                        )
                    )

                # Check subject casing
                if self.config.subject_case == "lower":
                    first_char = desc_stripped[0]
                    if first_char.isalpha() and not first_char.islower():
                        errors.append(
                            ValidationError(
                                code="SUBJECT_CASE_LOWER",
                                message="Commit description must start with a lowercase letter.",
                                line_number=1,
                                suggestion=first_char.lower() + desc_stripped[1:],
                                severity="error",
                            )
                        )
                elif self.config.subject_case == "sentence":
                    first_char = desc_stripped[0]
                    if first_char.isalpha() and not first_char.isupper():
                        errors.append(
                            ValidationError(
                                code="SUBJECT_CASE_SENTENCE",
                                message="Commit description must start with an uppercase letter.",
                                line_number=1,
                                suggestion=first_char.upper() + desc_stripped[1:],
                                severity="error",
                            )
                        )

        # 6. Header length limits
        if len(header) > self.config.max_header_length:
            errors.append(
                ValidationError(
                    code="MAX_HEADER_LENGTH",
                    message=(
                        f"Commit header length ({len(header)}) exceeds maximum "
                        f"limit of {self.config.max_header_length} characters."
                    ),
                    line_number=1,
                    severity="error",
                )
            )

        if len(header) < self.config.min_header_length:
            errors.append(
                ValidationError(
                    code="MIN_HEADER_LENGTH",
                    message=(
                        f"Commit header length ({len(header)}) is shorter than minimum "
                        f"limit of {self.config.min_header_length} characters."
                    ),
                    line_number=1,
                    severity="error",
                )
            )

        # 7. Body presence and line lengths
        if self.config.require_body and not commit.body:
            errors.append(
                ValidationError(
                    code="BODY_REQUIRED",
                    message="A commit body is required by configuration.",
                    line_number=3,
                    severity="error",
                )
            )

        if commit.body and self.config.max_body_line_length > 0:
            body_lines = commit.body.splitlines()
            for idx, bline in enumerate(body_lines):
                # Calculate approximate line number (header = 1, blank = 2, body starts at 3)
                approx_line = idx + 3
                if len(bline) > self.config.max_body_line_length:
                    # Ignore URL lines, markdown links, or long code lines
                    if self._is_exempt_line(bline):
                        continue
                    msg = (
                        f"Body line {approx_line} length ({len(bline)}) exceeds "
                        f"maximum limit of {self.config.max_body_line_length} characters."
                    )
                    err = ValidationError(
                        code="MAX_BODY_LINE_LENGTH",
                        message=msg,
                        line_number=approx_line,
                        severity="warning",
                    )
                    warnings.append(err)

        # 8. Treat warnings as errors if configured
        if self.config.warnings_as_errors and warnings:
            for w in warnings:
                w.severity = "error"
            errors.extend(warnings)
            warnings = []

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            commit=commit,
        )

    def _should_ignore(self, header: str) -> bool:
        """Check if commit header matches ignore rules."""
        if self.config.ignore_merge_commits:
            if header.startswith("Merge ") or header.startswith("Merge branch ") or header.startswith("Merge pull request "):
                return True

        if self.config.ignore_revert_commits:
            if header.startswith("Revert ") or header.startswith("revert "):
                return True

        for pattern in self.config.ignore_patterns:
            try:
                if re.match(pattern, header):
                    return True
            except re.error:
                continue

        return False

    def _diagnose_header_format(self, header: str) -> ValidationError:
        """Analyze a malformed header and construct a helpful error message and suggestion."""
        # Check missing space after colon: "feat:message"
        m_no_space = re.match(r"^([a-zA-Z0-9_\-]+(?:\([^()]+\))?!?):(\S.*)$", header)
        if m_no_space:
            prefix = m_no_space.group(1)
            rest = m_no_space.group(2)
            suggestion = f"{prefix}: {rest}"
            return ValidationError(
                code="MISSING_SPACE_AFTER_COLON",
                message=f"Missing space after colon in header. Expected format: '<type>(<scope>): <description>'.",
                line_number=1,
                column_number=len(prefix) + 1,
                suggestion=suggestion,
                severity="error",
            )

        # Check space before colon: "feat : description" or "feat(ui) : description"
        m_space_before_colon = re.match(r"^([a-zA-Z0-9_\-]+(?:\([^()]+\))?!?)\s+:\s*(.*)$", header)
        if m_space_before_colon:
            prefix = m_space_before_colon.group(1)
            rest = m_space_before_colon.group(2)
            suggestion = f"{prefix}: {rest}"
            return ValidationError(
                code="UNEXPECTED_WHITESPACE",
                message="Unexpected whitespace before colon in commit header.",
                line_number=1,
                suggestion=suggestion,
                severity="error",
            )

        # Check missing colon entirely: "feat something"
        tokens = header.split(None, 1)
        if tokens:
            potential_type = tokens[0].rstrip(":")
            if potential_type.lower() in self.config.types or potential_type.lower() in COMMON_TYPE_ALIASES:
                corr_type = COMMON_TYPE_ALIASES.get(potential_type.lower(), potential_type.lower())
                rest = tokens[1] if len(tokens) > 1 else "description"
                suggestion = f"{corr_type}: {rest}"
                return ValidationError(
                    code="MISSING_COLON",
                    message="Missing colon after commit type/scope.",
                    line_number=1,
                    column_number=len(tokens[0]),
                    suggestion=suggestion,
                    severity="error",
                )

        # Check unclosed scope: "feat(auth: description"
        if "(" in header and ")" not in header.split(":")[0]:
            return ValidationError(
                code="UNCLOSED_SCOPE",
                message="Unclosed parenthesis in scope.",
                line_number=1,
                suggestion="Ensure scope is enclosed in parentheses: type(scope): description",
                severity="error",
            )

        # General invalid header format
        return ValidationError(
            code="INVALID_HEADER_FORMAT",
            message=(
                f"Commit header does not match Conventional Commits format "
                f"'<type>(<scope>): <description>' or '<type>: <description>'."
            ),
            line_number=1,
            suggestion=f"feat: {header}",
            severity="error",
        )

    def _is_exempt_line(self, line: str) -> bool:
        """Check if body line is exempt from length limit (URLs, code blocks, tables)."""
        stripped = line.strip()
        # URLs or markdown links
        if re.search(r"https?://\S+", stripped):
            return True
        # Code fence
        if stripped.startswith("```") or stripped.startswith("`"):
            return True
        # Markdown table
        if stripped.startswith("|") and stripped.endswith("|"):
            return True
        return False


def validate_message(message: str, config: Optional[Config] = None) -> ValidationResult:
    """Convenience helper to validate a commit message string."""
    validator = Validator(config)
    return validator.validate(message)
