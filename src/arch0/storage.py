from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import ArchiveDecision, ArchiveOperationDecision, ArchiveRequest
from .validation import ensure_child_path, validate_project_name


@dataclass(frozen=True)
class StoredArchive:
    path: Path
    relative_path: str
    created_at: str
    modified_at: str
    title: str
    abstract: str | None


def archive_to_project(
    *,
    vault_dir: Path,
    project_name: str,
    request: ArchiveRequest,
    decision: ArchiveDecision,
) -> StoredArchive:
    clean_project = validate_project_name(project_name)
    now = _now_iso()
    project_dir = ensure_child_path(vault_dir, vault_dir / clean_project)
    archive_dir = ensure_child_path(vault_dir, project_dir / "archives")
    archive_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(request.archive_title) or first_h1_slug(request.archive_content) or "work-summary"
    final_path = unique_path(archive_dir / f"{slug}.md")
    write_archive_file(final_path, request.archive_content, created_at=now, modified_at=now)
    relative = final_path.relative_to(project_dir).as_posix()
    update_index(
        project_dir=project_dir,
        project_name=clean_project,
        created_at=now,
        modified_at=now,
        title=request.archive_title.strip(),
        abstract=decision.abstract or "",
        source=request.send_from_who.strip(),
        operation="created_archive",
        relative_path=relative,
    )
    return StoredArchive(final_path, final_path.as_posix(), now, now, request.archive_title.strip(), decision.abstract)


def update_archive_in_project(
    *,
    vault_dir: Path,
    project_name: str,
    request: ArchiveRequest,
    decision: ArchiveOperationDecision,
) -> StoredArchive:
    clean_project = validate_project_name(project_name)
    if not decision.target_archive_path or not decision.merged_content:
        raise ValueError("updated archive decision must include target path and merged content")

    project_dir = ensure_child_path(vault_dir, vault_dir / clean_project)
    final_path = ensure_child_path(project_dir, project_dir / decision.target_archive_path)
    if not final_path.exists():
        raise FileNotFoundError(f"target archive does not exist: {decision.target_archive_path}")

    existing_text = final_path.read_text(encoding="utf-8")
    created_at = read_front_matter_value(existing_text, "created_at") or _now_iso()
    modified_at = _now_iso()
    title = (decision.merged_title or request.archive_title).strip()
    write_archive_file(final_path, decision.merged_content, created_at=created_at, modified_at=modified_at)
    relative = final_path.relative_to(project_dir).as_posix()
    update_index(
        project_dir=project_dir,
        project_name=clean_project,
        created_at=created_at,
        modified_at=modified_at,
        title=title,
        abstract=decision.change_summary or decision.abstract or "",
        source=request.send_from_who.strip(),
        operation="updated_archive",
        relative_path=relative,
    )
    return StoredArchive(final_path, final_path.as_posix(), created_at, modified_at, title, decision.abstract)


def archive_to_needs_review(
    *,
    vault_dir: Path,
    request: ArchiveRequest,
) -> StoredArchive:
    now = _now_iso()
    review_dir = ensure_child_path(vault_dir, vault_dir / "inbox" / "needs-review")
    review_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(request.archive_title) or first_h1_slug(request.archive_content) or "work-summary"
    final_path = unique_path(review_dir / f"{slug}.md")
    write_archive_file(final_path, request.archive_content, created_at=now, modified_at=now)
    return StoredArchive(final_path, final_path.as_posix(), now, now, request.archive_title.strip(), None)


def write_archive_file(path: Path, content: str, *, created_at: str, modified_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f'---\ncreated_at: "{created_at}"\nmodified_at: "{modified_at}"\n---\n\n{content}'
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(body)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def update_index(
    *,
    project_dir: Path,
    project_name: str,
    created_at: str,
    modified_at: str,
    title: str,
    abstract: str,
    source: str,
    operation: str,
    relative_path: str,
) -> None:
    index_path = project_dir / "index.md"
    if not index_path.exists():
        index_path.write_text(
            f"# Project: {project_name}\n\n"
            "## Archived Documents\n\n"
            "| Created At | Modified At | Title | Abstract | Source | Operation | Path |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    row = (
        f"| {escape_table(created_at)} | {escape_table(modified_at)} | {escape_table(title)} | "
        f"{escape_table(abstract)} | {escape_table(source)} | {escape_table(operation)} | "
        f"{escape_table(relative_path)} |\n"
    )
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(row)


def list_existing_projects(vault_dir: Path) -> list[str]:
    if not vault_dir.exists():
        return []
    reserved = {"inbox", "audit"}
    return sorted(
        path.name
        for path in vault_dir.iterdir()
        if path.is_dir() and path.name.lower() not in reserved
    )


def read_index_snippets(vault_dir: Path, projects: list[str], *, max_chars: int = 2000) -> dict[str, str]:
    snippets: dict[str, str] = {}
    for project in projects:
        index_path = vault_dir / project / "index.md"
        if index_path.exists():
            snippets[project] = index_path.read_text(encoding="utf-8")[:max_chars]
    return snippets


def slugify(value: str) -> str:
    clean = value.strip().lower()
    clean = re.sub(r"[\\/]+", "-", clean)
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"[^a-z0-9._-]+", "", clean)
    clean = re.sub(r"[-_]{2,}", "-", clean).strip("-._")
    return clean[:80]


def first_h1_slug(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return slugify(line[2:])
    return ""


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for counter in range(2, 10_000):
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("could not find unique archive filename")


def escape_table(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()


def read_front_matter_value(markdown: str, key: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return None
    prefix = f"{key}:"
    for line in markdown[4:end].splitlines():
        if not line.startswith(prefix):
            continue
        return line.split(":", 1)[1].strip().strip('"')
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
