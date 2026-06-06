from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import ArchiveDecision, ArchiveRequest
from .storage import escape_table


def append_audit_log(
    *,
    vault_dir: Path,
    status: str,
    request: ArchiveRequest,
    decision: ArchiveDecision | None,
    stored_path: str | None,
    warnings: list[str],
) -> None:
    audit_dir = vault_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / "audit-log.md"
    timestamp = _now_iso()
    lines = [
        f"## {timestamp} {status}",
        "",
        f"- cmd_type: {request.cmd_type}",
        f"- archive_title: {escape_table(request.archive_title)}",
        f"- send_from_who: {escape_table(request.send_from_who)}",
    ]
    if decision is not None:
        lines.extend(
            [
                f"- project_name: {escape_table(decision.project_name or '')}",
                f"- confidence: {decision.confidence}",
                f"- reason: {escape_table(decision.reason)}",
            ]
        )
        if decision.abstract:
            lines.append(f"- abstract: {escape_table(decision.abstract)}")
    if stored_path:
        lines.append(f"- stored_path: {escape_table(stored_path)}")
    if warnings:
        lines.append(f"- warnings: {escape_table('; '.join(warnings))}")
    lines.append("")
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

