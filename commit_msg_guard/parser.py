"""Conventional Commits parser implementing specification v1.0.0."""

import re
from typing import List, Tuple, Optional, Dict, Any
from commit_msg_guard.models import ConventionalCommit

# Regex for standard Conventional Commit header
# Format: <type>[(scope)][!]: <description>
HEADER_PATTERN = re.compile(
    r"^(?P<type>[a-zA-Z0-9_\-]+)(?:\((?P<scope>[^()\r\n]+)\))?(?P<breaking>!)?:\s+(?P<description>.+)$"
)

# Loose regex to detect attempts at conventional commits (missing space, etc.)
LOOSE_HEADER_PATTERN = re.compile(
    r"^(?P<type>[a-zA-Z0-9_\-]+)(?:\((?P<scope>[^()\r\n]+)\))?(?P<breaking>!)?:(?P<description>.*)$"
)

# Footer pattern: <token>: <value> OR <token> #<value> OR BREAKING CHANGE: <value>
FOOTER_PATTERN = re.compile(
    r"^(?P<token>BREAKING CHANGE|BREAKING-CHANGE|[a-zA-Z0-9\-]+)(?::\s+|\s+#)(?P<value>.+)$"
)


class CommitParser:
    """Parses raw git commit message strings into structured ConventionalCommit objects."""

    def __init__(self, strip_comments: bool = True, comment_char: str = "#"):
        self.strip_comments = strip_comments
        self.comment_char = comment_char

    def parse(self, raw_message: str) -> ConventionalCommit:
        """Parse raw commit message string into ConventionalCommit."""
        raw_lines = raw_message.splitlines()

        # Filter out comments if enabled
        cleaned_lines: List[Tuple[int, str]] = []  # (original_0_based_line_idx, text)
        for idx, line in enumerate(raw_lines):
            if self.strip_comments and line.startswith(self.comment_char):
                continue
            cleaned_lines.append((idx, line))

        # Drop trailing empty lines
        while cleaned_lines and not cleaned_lines[-1][1].strip():
            cleaned_lines.pop()

        if not cleaned_lines:
            return ConventionalCommit(
                raw_message=raw_message,
                clean_message="",
                header="",
                raw_lines=raw_lines,
            )

        header_idx, header_line = cleaned_lines[0]
        header = header_line

        # Reconstruct clean text
        clean_text = "\n".join([line for _, line in cleaned_lines])

        commit = ConventionalCommit(
            raw_message=raw_message,
            clean_message=clean_text,
            header=header,
            raw_lines=raw_lines,
        )

        # Check if header matches standard regex
        match = HEADER_PATTERN.match(header)
        if match:
            commit.type = match.group("type")
            commit.scope = match.group("scope")
            commit.is_breaking = bool(match.group("breaking"))
            commit.description = match.group("description")
        else:
            # Try loose regex to populate partial fields if possible
            loose_match = LOOSE_HEADER_PATTERN.match(header)
            if loose_match:
                commit.type = loose_match.group("type")
                commit.scope = loose_match.group("scope")
                commit.is_breaking = bool(loose_match.group("breaking"))
                desc = loose_match.group("description")
                commit.description = desc.strip() if desc else None

        # Process rest of the lines (body & footers)
        if len(cleaned_lines) > 1:
            rest_lines = [line for _, line in cleaned_lines[1:]]
            body_lines, footers, breaking_in_footer = self._extract_body_and_footers(rest_lines)
            if body_lines:
                commit.body = "\n".join(body_lines).strip()
            commit.footers = footers
            if breaking_in_footer:
                commit.is_breaking = True

        return commit

    def _extract_body_and_footers(
        self, lines: List[str]
    ) -> Tuple[List[str], List[Tuple[str, str]], bool]:
        """Separate body paragraphs from footers."""
        # Find paragraphs
        paragraphs: List[List[str]] = []
        current: List[str] = []

        for line in lines:
            if not line.strip():
                if current:
                    paragraphs.append(current)
                    current = []
            else:
                current.append(line)
        if current:
            paragraphs.append(current)

        if not paragraphs:
            return [], [], False

        footers: List[Tuple[str, str]] = []
        has_breaking = False
        body_paragraphs: List[List[str]] = []

        # Check trailing paragraphs from the end to see if they are footers
        footer_paragraphs: List[List[str]] = []
        checking_footers = True

        for p in reversed(paragraphs):
            if checking_footers and self._is_footer_block(p):
                footer_paragraphs.insert(0, p)
            else:
                checking_footers = False
                body_paragraphs.insert(0, p)

        # Parse extracted footers
        for p in footer_paragraphs:
            parsed = self._parse_footer_paragraph(p)
            for token, val in parsed:
                footers.append((token, val))
                if token in ("BREAKING CHANGE", "BREAKING-CHANGE"):
                    has_breaking = True

        # Flatten body paragraphs with blank line separation
        flattened_body: List[str] = []
        for i, bp in enumerate(body_paragraphs):
            if i > 0:
                flattened_body.append("")
            flattened_body.extend(bp)

        return flattened_body, footers, has_breaking

    def _is_footer_block(self, lines: List[str]) -> bool:
        """Check if paragraph starts with a valid footer token."""
        if not lines:
            return False
        first_line = lines[0]
        return bool(FOOTER_PATTERN.match(first_line))

    def _parse_footer_paragraph(self, lines: List[str]) -> List[Tuple[str, str]]:
        """Parse footer lines which may contain one or multiple footers or multiline values."""
        results: List[Tuple[str, str]] = []
        current_token: Optional[str] = None
        current_value_lines: List[str] = []

        for line in lines:
            m = FOOTER_PATTERN.match(line)
            if m:
                if current_token:
                    results.append((current_token, "\n".join(current_value_lines).strip()))
                current_token = m.group("token")
                current_value_lines = [m.group("value")]
            else:
                if current_token:
                    current_value_lines.append(line)

        if current_token:
            results.append((current_token, "\n".join(current_value_lines).strip()))

        return results
