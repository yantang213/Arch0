from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from .models import RecallDocument, RecallResponse
from .validation import ValidationError, validate_project_name


def recall_project(vault_dir: Path, project_name: str, *, limit: int = 5) -> RecallResponse:
    decoded_name = validate_project_name(unquote(project_name))
    project_dir = vault_dir / decoded_name
    if not project_dir.exists() or not project_dir.is_dir():
        raise ValidationError("project_not_found", "project not found")

    index_path = project_dir / "index.md"
    index_markdown = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    archives_dir = project_dir / "archives"
    docs: list[RecallDocument] = []
    if archives_dir.exists():
        files = sorted(archives_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
        index_rows = parse_index_rows(index_markdown)
        for path in files[: max(0, min(limit, 20))]:
            markdown = path.read_text(encoding="utf-8")
            metadata = parse_front_matter(markdown)
            relative = path.relative_to(project_dir).as_posix()
            row = index_rows.get(relative, {})
            docs.append(
                RecallDocument(
                    path=path.as_posix(),
                    title=row.get("title") or title_from_markdown(markdown) or path.stem,
                    abstract=row.get("abstract"),
                    created_at=metadata.get("created_at"),
                    modified_at=metadata.get("modified_at"),
                    send_from_who=row.get("source"),
                    markdown=markdown,
                )
            )
    return RecallResponse(project_name=decoded_name, index_markdown=index_markdown, documents=docs)


def parse_front_matter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---\n"):
        return {}
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return {}
    metadata: dict[str, str] = {}
    for line in markdown[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def parse_index_rows(index_markdown: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in index_markdown.splitlines():
        if not line.startswith("| ") or line.startswith("| ---") or "Created At" in line:
            continue
        columns = [unescape_table(part.strip()) for part in line.strip("|").split("|")]
        if len(columns) != 5:
            continue
        _created_at, title, abstract, source, path = columns
        rows[path] = {"title": title, "abstract": abstract, "source": source}
    return rows


def unescape_table(value: str) -> str:
    return value.replace("\\|", "|")

