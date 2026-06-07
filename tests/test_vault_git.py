import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from arch0.vault_git import commit_vault, ensure_git_repo, is_worktree_clean


def require_git():
    if not shutil.which("git"):
        raise unittest.SkipTest("git binary is not installed")


class VaultGitTests(unittest.TestCase):
    def test_ensure_git_repo_initializes_repo_and_identity(self):
        require_git()
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            ensure_git_repo(vault)
            ensure_git_repo(vault)
            self.assertTrue((vault / ".git").exists())
            name = subprocess.check_output(["git", "config", "user.name"], cwd=vault, text=True).strip()
            email = subprocess.check_output(["git", "config", "user.email"], cwd=vault, text=True).strip()
            self.assertEqual("Arch0", name)
            self.assertEqual("arch0@local", email)

    def test_worktree_clean_and_commit(self):
        require_git()
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            ensure_git_repo(vault)
            self.assertTrue(is_worktree_clean(vault))

            note = vault / "note.md"
            note.write_text("v1\n", encoding="utf-8")
            self.assertFalse(is_worktree_clean(vault))

            commit = commit_vault(vault, "archive: create note")
            self.assertIsNotNone(commit)
            self.assertTrue(is_worktree_clean(vault))

            note.write_text("v2\n", encoding="utf-8")
            second_commit = commit_vault(vault, "archive: update note")
            self.assertIsNotNone(second_commit)
            history = subprocess.check_output(["git", "log", "--oneline", "--", "note.md"], cwd=vault, text=True)
            self.assertEqual(2, len([line for line in history.splitlines() if line.strip()]))
            old_text = subprocess.check_output(["git", "show", f"{commit}:note.md"], cwd=vault, text=True)
            self.assertEqual("v1\n", old_text)


if __name__ == "__main__":
    unittest.main()
