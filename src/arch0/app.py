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
    ArchiveRequest,
    ArchiveResponse,
    DecisionDetail,
    HealthResponse,
    RecallResponse,
)
from .recall import recall_project
from .safety import scan_for_secrets
from .storage import archive_to_needs_review, archive_to_project, list_existing_projects, read_index_snippets
from .validation import ValidationError, validate_archive_request_shape


write_lock = threading.Lock()


def create_app(
    *,
    settings: Settings | None = None,
    decision_engine: ArchiveDecisionEngine | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    engine = decision_engine or LLMApiDecisionEngine(settings)
    app = FastAPI(title="Arch0", version="0.1.0")
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
                append_audit_log(
                    vault_dir=current.vault_dir,
                    status="rejected",
                    request=request,
                    decision=decision,
                    stored_path=None,
                    warnings=warnings,
                )
                return response_from_decision(
                    decision,
                    stored_path=None,
                    index_updated=False,
                    audit_logged=True,
                    warnings=warnings,
                )

            current.vault_dir.mkdir(parents=True, exist_ok=True)
            existing_projects = list_existing_projects(current.vault_dir)
            context = ArchiveDecisionContext(
                existing_projects=existing_projects,
                project_index_snippets=read_index_snippets(current.vault_dir, existing_projects),
            )
            try:
                decision = app.state.decision_engine.decide(request, context)
            except DecisionEngineError as exc:
                raise HTTPException(status_code=500, detail={"code": "decision_engine_failed", "message": str(exc)}) from exc

            with write_lock:
                if decision.status == "accepted":
                    if not decision.project_name:
                        raise HTTPException(status_code=500, detail={"code": "decision_engine_failed"})
                    stored = archive_to_project(
                        vault_dir=current.vault_dir,
                        project_name=decision.project_name,
                        request=request,
                        decision=decision,
                    )
                    append_audit_log(
                        vault_dir=current.vault_dir,
                        status="accepted",
                        request=request,
                        decision=decision,
                        stored_path=stored.relative_path,
                        warnings=warnings,
                    )
                    return response_from_decision(
                        decision,
                        stored_path=stored.relative_path,
                        index_updated=True,
                        audit_logged=True,
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
                    return response_from_decision(
                        decision,
                        stored_path=stored.relative_path,
                        index_updated=False,
                        audit_logged=True,
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
                return response_from_decision(
                    decision,
                    stored_path=None,
                    index_updated=False,
                    audit_logged=True,
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
    stored_path: str | None,
    index_updated: bool,
    audit_logged: bool,
    warnings: list[str],
) -> ArchiveResponse:
    return ArchiveResponse(
        status=decision.status,
        project_name=decision.project_name if decision.status == "accepted" else None,
        decision_detail=DecisionDetail(
            confidence=decision.confidence,
            reason=decision.reason,
            abstract=decision.abstract,
        ),
        stored_path=stored_path,
        index_updated=index_updated,
        audit_logged=audit_logged,
        warnings=warnings,
    )


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
