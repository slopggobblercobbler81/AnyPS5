"""commit-msg-guard: Production-grade Conventional Commits validator and git hook utility."""

__version__ = "1.0.0"
__author__ = "slopggobblercobbler81"
__all__ = [
    "validate_message",
    "ConventionalCommit",
    "ValidationResult",
    "ValidationError",
    "Config",
]

from commit_msg_guard.models import ConventionalCommit, ValidationError, ValidationResult
from commit_msg_guard.config import Config
from commit_msg_guard.validator import validate_message
