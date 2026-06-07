from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import ValidationError as PydanticValidationError

from .config import Settings
from .models import ArchiveDecision, ArchiveDecisionContext, ArchiveOperationDecision, ArchiveRequest
from .validation import ValidationError, validate_project_name


class DecisionEngineError(Exception):
    pass


class ArchiveDecisionEngine(Protocol):
    def decide(self, request: ArchiveRequest, context: ArchiveDecisionContext) -> ArchiveDecision:
        ...


class LLMApiDecisionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def decide(self, request: ArchiveRequest, context: ArchiveDecisionContext) -> ArchiveDecision:
        if not self.settings.llm_api_key:
            raise DecisionEngineError("ARCH0_LLM_API_KEY is required for LLMApiDecisionEngine")
        prompt = build_prompt(request, context)
        raw_content = self._call_chat_completions(prompt)
        return parse_decision(raw_content)

    def decide_operation(self, request: ArchiveRequest, context: ArchiveDecisionContext) -> ArchiveOperationDecision:
        if not self.settings.llm_api_key:
            raise DecisionEngineError("ARCH0_LLM_API_KEY is required for LLMApiDecisionEngine")
        prompt = build_operation_prompt(request, context)
        raw_content = self._call_chat_completions(prompt)
        return parse_operation_decision(raw_content)

    def _call_chat_completions(self, prompt: str) -> str:
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Arch Agent's archive decision engine. Return only strict JSON. "
                        "Do not rewrite the archive body."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DecisionEngineError(f"LLM API call failed: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DecisionEngineError("LLM API response did not contain message content") from exc


def build_prompt(request: ArchiveRequest, context: ArchiveDecisionContext) -> str:
    project_lines = []
    for project in context.existing_projects:
        snippet = context.project_index_snippets.get(project, "").strip()
        if snippet:
            project_lines.append(f"- {project}\n  index snippet: {snippet[:1200]}")
        else:
            project_lines.append(f"- {project}")
    projects = "\n".join(project_lines) if project_lines else "(none)"
    instruction = request.instruction or "(none)"
    content = request.archive_content[:20_000]
    return f"""Decide how Arch0 should handle this archive request.

Return strict JSON with this shape:
{{
  "status": "accepted" | "needs_review" | "rejected",
  "project_name": string | null,
  "confidence": "low" | "medium" | "high",
  "reason": "short reason",
  "abstract": "one or two sentence abstract"
}}

Rules:
- Use status=accepted only when this is suitable long-term project memory and you can choose a project name.
- Use an existing project name when the content clearly belongs to one.
- Create a concise human-readable project name when the content clearly defines a new project.
- Use needs_review when useful but ambiguous.
- Use rejected when the content is not suitable long-term project memory.
- Do not return filesystem paths.
- Do not invent document categories.

Existing projects:
{projects}

Request:
cmd_type: {request.cmd_type}
archive_title: {request.archive_title}
send_from_who: {request.send_from_who}
instruction: {instruction}

Archive content:
{content}
"""


def build_operation_prompt(request: ArchiveRequest, context: ArchiveDecisionContext) -> str:
    project_lines = []
    for project in context.existing_projects:
        snippet = context.project_index_snippets.get(project, "").strip()
        if snippet:
            project_lines.append(f"- {project}\n  index snippet: {snippet[:2000]}")
        else:
            project_lines.append(f"- {project}")
    projects = "\n".join(project_lines) if project_lines else "(none)"
    instruction = request.instruction or "(none)"
    content = request.archive_content[:20_000]
    return f"""Decide how Arch0 should handle this submitted memory.

Return strict JSON with this shape:
{{
  "status": "accepted" | "needs_review" | "rejected",
  "operation": "created_archive" | "updated_archive" | "needs_review" | "rejected",
  "project_name": string | null,
  "confidence": "low" | "medium" | "high",
  "reason": "short reason",
  "abstract": "one or two sentence abstract",
  "target_archive_path": string | null,
  "merged_title": string | null,
  "merged_content": string | null,
  "change_summary": string | null
}}

Rules:
- The client is only submitting memory. Do not treat cmd_type as the true insert/update decision.
- Use operation=created_archive when the submitted memory should become a new Markdown archive.
- Use operation=updated_archive only when confidence is high, the target archive is clearly identified under archives/, and merged_content fully rewrites the target Markdown body.
- Use operation=needs_review when the memory is useful but placement or merge behavior is ambiguous.
- Use operation=rejected when the content is not suitable long-term project memory.
- Use an existing project name when the memory clearly belongs to one.
- Create a concise human-readable project name when the memory clearly defines a new project.
- Do not invent document categories.

Existing projects and index snippets:
{projects}

Request:
cmd_type: {request.cmd_type}
archive_title: {request.archive_title}
send_from_who: {request.send_from_who}
instruction: {instruction}

Archive content:
{content}
"""


def parse_decision(raw: str) -> ArchiveDecision:
    try:
        data = json.loads(raw)
        decision = ArchiveDecision.model_validate(data)
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        raise DecisionEngineError(f"Invalid decision JSON: {exc}") from exc

    if decision.status == "accepted":
        if not decision.project_name:
            raise DecisionEngineError("Accepted decision requires project_name")
        try:
            validated_name = validate_project_name(decision.project_name)
        except ValidationError as exc:
            raise DecisionEngineError(exc.message) from exc
        return decision.model_copy(update={"project_name": validated_name})

    return decision.model_copy(update={"project_name": None})


def parse_operation_decision(raw: str) -> ArchiveOperationDecision:
    try:
        data = json.loads(raw)
        decision = ArchiveOperationDecision.model_validate(data)
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        raise DecisionEngineError(f"Invalid operation decision JSON: {exc}") from exc

    if decision.status == "accepted":
        if not decision.project_name:
            raise DecisionEngineError("Accepted decision requires project_name")
        try:
            validated_name = validate_project_name(decision.project_name)
        except ValidationError as exc:
            raise DecisionEngineError(exc.message) from exc
        return decision.model_copy(update={"project_name": validated_name})

    return decision.model_copy(update={"project_name": None, "target_archive_path": None})


class StaticDecisionEngine:
    """Test helper and simple injected implementation."""

    def __init__(self, decision: ArchiveDecision):
        self.decision = decision
        self.calls = 0

    def decide(self, request: ArchiveRequest, context: ArchiveDecisionContext) -> ArchiveDecision:
        self.calls += 1
        return self.decision
