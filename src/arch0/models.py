from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Status = Literal["accepted", "needs_review", "rejected"]
Confidence = Literal["low", "medium", "high"]


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cmd_type: Literal["insert"]
    archive_title: str = Field(min_length=1, max_length=200)
    archive_content: str
    send_from_who: str = Field(min_length=1, max_length=300)
    instruction: str | None = Field(default=None, max_length=4096)


class DecisionDetail(BaseModel):
    confidence: Confidence
    reason: str = Field(min_length=1, max_length=2000)
    abstract: str | None = Field(default=None, max_length=1000)


class ArchiveResponse(BaseModel):
    status: Status
    project_name: str | None
    decision_detail: DecisionDetail
    stored_path: str | None
    index_updated: bool
    audit_logged: bool
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class RecallDocument(BaseModel):
    path: str
    title: str
    abstract: str | None
    created_at: str | None
    modified_at: str | None
    send_from_who: str | None
    markdown: str


class RecallResponse(BaseModel):
    project_name: str
    index_markdown: str
    documents: list[RecallDocument]


@dataclass(frozen=True)
class ArchiveDecisionContext:
    existing_projects: list[str]
    project_index_snippets: dict[str, str]


class ArchiveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    project_name: str | None = None
    confidence: Confidence
    reason: str = Field(min_length=1, max_length=2000)
    abstract: str | None = Field(default=None, max_length=1000)

