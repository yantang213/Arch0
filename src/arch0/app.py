from __future__ import annotations

import threading
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .audit import append_audit_log
from .config import Settings, load_settings
from .decision_engine import ArchiveDecisionEngine, DecisionEngineError, LLMApiDecisionEngine
from .models import (
    ArchiveDecision,
    ArchiveDecisionContext,
    ArchiveOperationDecision,
    ArchiveRequest,
    ArchiveResponse,
    DecisionDetail,
    HealthResponse,
    RecallResponse,
)
from .recall import recall_project
from .safety import scan_for_secrets
from .storage import archive_to_needs_review, archive_to_project, list_existing_projects, read_index_snippets, update_archive_in_project
from .validation import ValidationError, validate_archive_request_shape
from .vault_git import VaultGitError, commit_vault, ensure_git_repo, is_worktree_clean


write_lock = threading.Lock()


def create_app(
    *,
    settings: Settings | None = None,
    decision_engine: ArchiveDecisionEngine | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    engine = decision_engine or LLMApiDecisionEngine(settings)
    app = FastAPI(title="Arch0", version="0.18.0")
    app.state.settings = settings
    app.state.decision_engine = engine

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_request, exc: RequestValidationError):
        first_error = exc.errors()[0] if exc.errors() else {}
        location = first_error.get("loc", [])
        field = str(location[-1]) if location else "request"
        error_type = str(first_error.get("type", "invalid_request"))
        code = validation_error_code(field, error_type)
        return JSONResponse(status_code=400, content={"detail": {"code": code, "message": first_error.get("msg", "Invalid request")}})

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        current: Settings = app.state.settings
        if not current.requires_auth:
            return
        expected = f"Bearer {current.api_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail={"code": "unauthorized"})

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/v0.1/archives", response_model=ArchiveResponse, dependencies=[Depends(require_auth)])
    def submit_archive(request: ArchiveRequest) -> ArchiveResponse:
        current: Settings = app.state.settings
        warnings: list[str] = []
        try:
            warnings.extend(
                validate_archive_request_shape(
                    archive_title=request.archive_title,
                    archive_content=request.archive_content,
                    send_from_who=request.send_from_who,
                    settings=current,
                )
            )
            findings = scan_for_secrets(request.archive_content)
            if findings:
                warnings.extend(finding.message for finding in findings)
                decision = ArchiveDecision(
                    status="rejected",
                    project_name=None,
                    confidence="high",
                    reason="Detected suspected secret material before decision engine routing.",
                    abstract=None,
                )
                with write_lock:
                    try:
                        ensure_git_repo(current.vault_dir)
                        dirty_before_audit = not is_worktree_clean(current.vault_dir)
                    except VaultGitError as exc:
                        raise HTTPException(status_code=500, detail={"code": "vault_git_failed", "message": str(exc)}) from exc
                    append_audit_log(
                        vault_dir=current.vault_dir,
                        status="rejected",
                        request=request,
                        decision=decision,
                        stored_path=None,
                        warnings=warnings,
                    )
                    git_commit = None
                    if not dirty_before_audit:
                        git_commit = commit_current_vault(current.vault_dir, "rejected", request.archive_title)
                return response_from_decision(
                    decision,
                    operation="rejected",
                    stored_path=None,
                    index_updated=False,
                    audit_logged=True,
                    git_committed=git_commit is not None,
                    git_commit=git_commit,
                    warnings=warnings,
                )

            with write_lock:
                try:
                    ensure_git_repo(current.vault_dir)
                except VaultGitError as exc:
                    raise HTTPException(status_code=500, detail={"code": "vault_git_failed", "message": str(exc)}) from exc

                if not is_worktree_clean(current.vault_dir):
                    warnings.append("Vault has uncommitted changes.")
                    review_decision = ArchiveOperationDecision(
                        status="needs_review",
                        operation="needs_review",
                        project_name=None,
                        confidence="high",
                        reason="Vault has uncommitted changes; Arch0 will not write project archives automatically.",
                        abstract="Stored for manual review because the vault worktree is dirty.",
                    )
                    stored = archive_to_needs_review(vault_dir=current.vault_dir, request=request)
                    append_audit_log(
                        vault_dir=current.vault_dir,
                        status="needs_review",
                        request=request,
                        decision=review_decision,
                        stored_path=stored.relative_path,
                        warnings=warnings,
                    )
                    return response_from_operation_decision(
                        review_decision,
                        stored_path=stored.relative_path,
                        index_updated=False,
                        audit_logged=True,
                        git_committed=False,
                        git_commit=None,
                        warnings=warnings,
                    )

                existing_projects = list_existing_projects(current.vault_dir)
                context = ArchiveDecisionContext(
                    existing_projects=existing_projects,
                    project_index_snippets=read_index_snippets(current.vault_dir, existing_projects),
                )
                try:
                    decision = decide_operation(app.state.decision_engine, request, context)
                except DecisionEngineError as exc:
                    raise HTTPException(status_code=500, detail={"code": "decision_engine_failed", "message": str(exc)}) from exc

                if decision.status == "accepted":
                    if not decision.project_name:
                        raise HTTPException(status_code=500, detail={"code": "decision_engine_failed"})
                    if decision.operation == "updated_archive":
                        stored = update_archive_in_project(
                            vault_dir=current.vault_dir,
                            project_name=decision.project_name,
                            request=request,
                            decision=decision,
                        )
                    else:
                        legacy_decision = ArchiveDecision(
                            status=decision.status,
                            project_name=decision.project_name,
                            confidence=decision.confidence,
                            reason=decision.reason,
                            abstract=decision.abstract,
                        )
                        stored = archive_to_project(
                            vault_dir=current.vault_dir,
                            project_name=decision.project_name,
                            request=request,
                            decision=legacy_decision,
                        )
                    append_audit_log(
                        vault_dir=current.vault_dir,
                        status="accepted",
                        request=request,
                        decision=decision,
                        stored_path=stored.relative_path,
                        warnings=warnings,
                    )
                    git_commit = commit_current_vault(current.vault_dir, decision.operation, request.archive_title)
                    return response_from_operation_decision(
                        decision,
                        stored_path=stored.relative_path,
                        index_updated=True,
                        audit_logged=True,
                        git_committed=git_commit is not None,
                        git_commit=git_commit,
                        warnings=warnings,
                    )

                if decision.status == "needs_review":
                    stored = archive_to_needs_review(vault_dir=current.vault_dir, request=request)
                    warnings.append("Project routing is ambiguous.")
                    append_audit_log(
                        vault_dir=current.vault_dir,
                        status="needs_review",
                        request=request,
                        decision=decision,
                        stored_path=stored.relative_path,
                        warnings=warnings,
                    )
                    git_commit = commit_current_vault(current.vault_dir, "needs_review", request.archive_title)
                    return response_from_operation_decision(
                        decision,
                        stored_path=stored.relative_path,
                        index_updated=False,
                        audit_logged=True,
                        git_committed=git_commit is not None,
                        git_commit=git_commit,
                        warnings=warnings,
                    )

                append_audit_log(
                    vault_dir=current.vault_dir,
                    status="rejected",
                    request=request,
                    decision=decision,
                    stored_path=None,
                    warnings=warnings,
                )
                git_commit = commit_current_vault(current.vault_dir, "rejected", request.archive_title)
                return response_from_operation_decision(
                    decision,
                    stored_path=None,
                    index_updated=False,
                    audit_logged=True,
                    git_committed=git_commit is not None,
                    git_commit=git_commit,
                    warnings=warnings,
                )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    @app.get("/v0.1/recall/{project_name}", response_model=RecallResponse, dependencies=[Depends(require_auth)])
    def recall(project_name: str, limit: int = Query(default=5, ge=1, le=20)) -> RecallResponse:
        try:
            return recall_project(app.state.settings.vault_dir, project_name, limit=limit)
        except ValidationError as exc:
            status = 404 if exc.code == "project_not_found" else 400
            raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc

    return app


def response_from_decision(
    decision: ArchiveDecision,
    *,
    operation: str,
    stored_path: str | None,
    index_updated: bool,
    audit_logged: bool,
    git_committed: bool,
    git_commit: str | None,
    warnings: list[str],
) -> ArchiveResponse:
    return ArchiveResponse(
        status=decision.status,
        operation=operation,
        project_name=decision.project_name if decision.status == "accepted" else None,
        decision_detail=DecisionDetail(
            confidence=decision.confidence,
            reason=decision.reason,
            abstract=decision.abstract,
        ),
        stored_path=stored_path,
        index_updated=index_updated,
        audit_logged=audit_logged,
        git_committed=git_committed,
        git_commit=git_commit,
        warnings=warnings,
    )


def response_from_operation_decision(
    decision: ArchiveOperationDecision,
    *,
    stored_path: str | None,
    index_updated: bool,
    audit_logged: bool,
    git_committed: bool,
    git_commit: str | None,
    warnings: list[str],
) -> ArchiveResponse:
    return ArchiveResponse(
        status=decision.status,
        operation=decision.operation,
        project_name=decision.project_name if decision.status == "accepted" else None,
        decision_detail=DecisionDetail(
            confidence=decision.confidence,
            reason=decision.reason,
            abstract=decision.abstract,
            target_archive_path=decision.target_archive_path,
            change_summary=decision.change_summary,
        ),
        stored_path=stored_path,
        index_updated=index_updated,
        audit_logged=audit_logged,
        git_committed=git_committed,
        git_commit=git_commit,
        warnings=warnings,
    )


def decide_operation(engine, request: ArchiveRequest, context: ArchiveDecisionContext) -> ArchiveOperationDecision:
    if hasattr(engine, "decide_operation"):
        return engine.decide_operation(request, context)

    legacy_decision = engine.decide(request, context)
    if legacy_decision.status == "accepted":
        return ArchiveOperationDecision(
            status="accepted",
            operation="created_archive",
            project_name=legacy_decision.project_name,
            confidence=legacy_decision.confidence,
            reason=legacy_decision.reason,
            abstract=legacy_decision.abstract,
        )
    if legacy_decision.status == "needs_review":
        return ArchiveOperationDecision(
            status="needs_review",
            operation="needs_review",
            project_name=None,
            confidence=legacy_decision.confidence,
            reason=legacy_decision.reason,
            abstract=legacy_decision.abstract,
        )
    return ArchiveOperationDecision(
        status="rejected",
        operation="rejected",
        project_name=None,
        confidence=legacy_decision.confidence,
        reason=legacy_decision.reason,
        abstract=legacy_decision.abstract,
    )


def commit_current_vault(vault_dir: Path, operation: str, title: str) -> str | None:
    try:
        return commit_vault(vault_dir, f"archive: {operation} {title.strip()}")
    except VaultGitError as exc:
        raise HTTPException(status_code=500, detail={"code": "vault_git_failed", "message": str(exc)}) from exc


def validation_error_code(field: str, error_type: str) -> str:
    if field == "cmd_type":
        return "invalid_cmd_type"
    if field == "archive_title":
        return "archive_title_required"
    if field == "archive_content":
        return "archive_content_required"
    if field == "send_from_who":
        return "send_from_who_required"
    return error_type


app = create_app()
