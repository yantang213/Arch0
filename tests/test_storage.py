import tempfile
import unittest
from pathlib import Path

from arch0.models import ArchiveDecision, ArchiveRequest
from arch0.storage import archive_to_needs_review, archive_to_project


class StorageTests(unittest.TestCase):
    def make_request(self) -> ArchiveRequest:
        return ArchiveRequest(
            cmd_type="insert",
            archive_title="Nginx HTTPS setup",
            archive_content="# Nginx HTTPS setup\n\n" + "A" * 120,
            send_from_who="remote-agent:agent-b@vps-prod",
            instruction="Archive this.",
        )

    def make_decision(self) -> ArchiveDecision:
        return ArchiveDecision(
            status="accepted",
            project_name="my-vps-blog",
            confidence="high",
            reason="Matches project.",
            abstract="Documents Nginx HTTPS setup.",
        )

    def test_archive_to_project_writes_front_matter_body_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            request = self.make_request()
            stored = archive_to_project(
                vault_dir=vault,
                project_name="my-vps-blog",
                request=request,
                decision=self.make_decision(),
            )

            archive_path = Path(stored.relative_path)
            self.assertTrue(archive_path.exists())
            text = archive_path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\ncreated_at:"))
            self.assertTrue(text.endswith(request.archive_content))
            self.assertEqual(vault / "my-vps-blog" / "archives" / "nginx-https-setup.md", archive_path)

            index_text = (vault / "my-vps-blog" / "index.md").read_text(encoding="utf-8")
            self.assertIn("| Created At | Title | Abstract | Source | Path |", index_text)
            self.assertIn("Documents Nginx HTTPS setup.", index_text)
            self.assertIn("archives/nginx-https-setup.md", index_text)

    def test_archive_to_project_avoids_filename_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            request = self.make_request()
            decision = self.make_decision()
            first = archive_to_project(vault_dir=vault, project_name="my-vps-blog", request=request, decision=decision)
            second = archive_to_project(vault_dir=vault, project_name="my-vps-blog", request=request, decision=decision)
            self.assertNotEqual(first.relative_path, second.relative_path)
            self.assertTrue(second.relative_path.endswith("nginx-https-setup-2.md"))

    def test_archive_to_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            stored = archive_to_needs_review(vault_dir=vault, request=self.make_request())
            self.assertEqual(vault / "inbox" / "needs-review" / "nginx-https-setup.md", Path(stored.relative_path))
            self.assertTrue(Path(stored.relative_path).exists())


if __name__ == "__main__":
    unittest.main()

