from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyFinding:
    code: str
    message: str


PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
GITHUB_TOKEN_RE = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")
JWT_NEAR_TOKEN_RE = re.compile(
    r"(?i)\b(?:token|authorization|bearer)\b.{0,40}\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\b\s*[:=]\s*[\"']?([A-Za-z0-9_./+=-]{24,})[\"']?"
)


def scan_for_secrets(markdown: str) -> list[SafetyFinding]:
    checks = [
        (PRIVATE_KEY_RE, "private_key", "Detected private key marker."),
        (OPENAI_KEY_RE, "openai_key", "Detected OpenAI-style API key."),
        (GITHUB_TOKEN_RE, "github_token", "Detected GitHub token."),
        (AWS_ACCESS_KEY_RE, "aws_access_key", "Detected AWS access key ID."),
        (SLACK_TOKEN_RE, "slack_token", "Detected Slack token."),
        (JWT_NEAR_TOKEN_RE, "jwt_token", "Detected JWT-looking token near auth wording."),
    ]
    findings: list[SafetyFinding] = []
    for pattern, code, message in checks:
        if pattern.search(markdown):
            findings.append(SafetyFinding(code, message))

    for match in SECRET_ASSIGNMENT_RE.finditer(markdown):
        value = match.group(1)
        if _looks_like_secret_value(value):
            findings.append(SafetyFinding("secret_assignment", "Detected high-entropy secret assignment."))
            break

    return findings


def _looks_like_secret_value(value: str) -> bool:
    if len(value) < 24:
        return False
    distinct_classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[_./+=-]")
    )
    return distinct_classes >= 3

