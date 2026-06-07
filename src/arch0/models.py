from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    target_archive_path: str | None = None
    change_summary: str | None = Field(default=None, max_length=2000)


class ArchiveResponse(BaseModel):
    status: Status
    operation: str
    project_name: str | None
    decision_detail: DecisionDetail
    stored_path: str | None
    index_updated: bool
    audit_logged: bool
    git_committed: bool = False
    git_commit: str | None = None
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


ArchiveOperation = Literal["created_archive", "updated_archive", "needs_review", "rejected"]


class ArchiveOperationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    operation: ArchiveOperation
    project_name: str | None = None
    confidence: Confidence
    reason: str = Field(min_length=1, max_length=2000)
    abstract: str | None = Field(default=None, max_length=1000)
    target_archive_path: str | None = None
    merged_title: str | None = Field(default=None, max_length=200)
    merged_content: str | None = None
    change_summary: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_operation(self) -> ArchiveOperationDecision:
        if self.operation == "created_archive":
            if self.status != "accepted":
                raise ValueError("created_archive requires accepted status")
            if not self.project_name:
                raise ValueError("created_archive requires project_name")
            return self

        if self.operation == "updated_archive":
            if self.status != "accepted":
                raise ValueError("updated_archive requires accepted status")
            if self.confidence != "high":
                raise ValueError("updated_archive requires high confidence")
            if not self.project_name:
                raise ValueError("updated_archive requires project_name")
            if not self.target_archive_path:
                raise ValueError("updated_archive requires target_archive_path")
            if not self.merged_content:
                raise ValueError("updated_archive requires merged_content")
            if not self.change_summary:
                raise ValueError("updated_archive requires change_summary")
            _validate_relative_archive_path(self.target_archive_path)
            return self

        if self.operation == "needs_review":
            if self.status != "needs_review":
                raise ValueError("needs_review operation requires needs_review status")
            return self

        if self.operation == "rejected" and self.status != "rejected":
            raise ValueError("rejected operation requires rejected status")

        return self


def _validate_relative_archive_path(path: str) -> None:
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute():
        raise ValueError("target_archive_path must be relative")
    if ".." in pure_path.parts:
        raise ValueError("target_archive_path cannot contain parent traversal")
    if len(pure_path.parts) < 2 or pure_path.parts[0] != "archives":
        raise ValueError("target_archive_path must be under archives/")
    if pure_path.suffix != ".md":
        raise ValueError("target_archive_path must point to a Markdown file")
