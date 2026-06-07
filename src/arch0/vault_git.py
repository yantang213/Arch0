from __future__ import annotations

import subprocess
from pathlib import Path


class VaultGitError(RuntimeError):
    pass


def ensure_git_repo(vault_dir: Path) -> None:
    vault_dir.mkdir(parents=True, exist_ok=True)
    if not (vault_dir / ".git").exists():
        _run_git(vault_dir, "init")
    _run_git(vault_dir, "config", "user.name", "Arch0")
    _run_git(vault_dir, "config", "user.email", "arch0@local")


def is_worktree_clean(vault_dir: Path) -> bool:
    result = _run_git(vault_dir, "status", "--porcelain")
    return result.stdout.strip() == ""


def commit_vault(vault_dir: Path, message: str, paths: list[str | Path] | None = None) -> str | None:
    ensure_git_repo(vault_dir)
    if paths:
        _run_git(vault_dir, "add", "--", *[_to_git_path(vault_dir, path) for path in paths])
    else:
        _run_git(vault_dir, "add", "-A")

    if is_worktree_clean(vault_dir):
        return None

    _run_git(vault_dir, "commit", "-m", message)
    result = _run_git(vault_dir, "rev-parse", "HEAD")
    return result.stdout.strip()


def _to_git_path(vault_dir: Path, path: str | Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.relative_to(vault_dir).as_posix()
    return candidate.as_posix()


def _run_git(vault_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=vault_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise VaultGitError(message)
    return result
