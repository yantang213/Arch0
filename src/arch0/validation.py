from __future__ import annotations

from pathlib import Path

from .config import Settings


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


RESERVED_PROJECT_NAMES = {"inbox", "audit"}


def validate_archive_request_shape(
    *,
    archive_content: str,
    send_from_who: str,
    archive_title: str,
    settings: Settings,
) -> list[str]:
    warnings: list[str] = []
    content_bytes = len(archive_content.encode("utf-8"))
    if not archive_title.strip():
        raise ValidationError("archive_title_required", "archive_title is required")
    if not send_from_who.strip():
        raise ValidationError("send_from_who_required", "send_from_who is required")
    if not archive_content.strip():
        raise ValidationError("archive_content_required", "archive_content is required")
    if len(archive_content.strip()) < settings.min_archive_content_length:
        raise ValidationError(
            "archive_content_too_short",
            f"archive_content must be at least {settings.min_archive_content_length} characters",
        )
    if content_bytes > settings.max_archive_content_bytes:
        raise ValidationError(
            "archive_content_too_large",
            f"archive_content must be at most {settings.max_archive_content_bytes} bytes",
        )
    if not _has_markdown_h1(archive_content):
        warnings.append("No Markdown H1 found.")
    if len(archive_title.strip()) < 4:
        warnings.append("Archive title is very short.")
    return warnings


def validate_project_name(project_name: str) -> str:
    clean = project_name.strip()
    if not clean:
        raise ValidationError("invalid_project_name", "project_name is required")
    if len(clean) > 120:
        raise ValidationError("invalid_project_name", "project_name is too long")
    lowered = clean.lower()
    if lowered in RESERVED_PROJECT_NAMES:
        raise ValidationError("invalid_project_name", "project_name is reserved")
    if any(ch in clean for ch in ("/", "\\", "~")):
        raise ValidationError("invalid_project_name", "project_name contains unsafe characters")
    if ".." in clean:
        raise ValidationError("invalid_project_name", "project_name contains path traversal")
    if any(ord(ch) < 32 for ch in clean):
        raise ValidationError("invalid_project_name", "project_name contains control characters")
    return clean


def ensure_child_path(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValidationError("unsafe_path", "resolved path escapes vault")
    return candidate


def _has_markdown_h1(markdown: str) -> bool:
    return any(line.startswith("# ") for line in markdown.splitlines())

