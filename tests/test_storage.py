import tempfile
import unittest
from pathlib import Path

from arch0.models import ArchiveDecision, ArchiveOperationDecision, ArchiveRequest
from arch0.storage import archive_to_needs_review, archive_to_project, update_archive_in_project


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
            self.assertIn("| Created At | Modified At | Title | Abstract | Source | Operation | Path |", index_text)
            self.assertIn("Documents Nginx HTTPS setup.", index_text)
            self.assertIn("created_archive", index_text)
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

    def test_update_archive_in_project_modifies_same_file_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            request = self.make_request()
            created = archive_to_project(
                vault_dir=vault,
                project_name="my-vps-blog",
                request=request,
                decision=self.make_decision(),
            )
            original_text = created.path.read_text(encoding="utf-8")
            original_created_at = created.created_at

            update_request = ArchiveRequest(
                cmd_type="insert",
                archive_title="Nginx HTTPS troubleshooting",
                archive_content="# Nginx HTTPS troubleshooting\n\nUpdated input.",
                send_from_who="remote-agent:agent-b@vps-prod",
                instruction="Merge into existing setup notes.",
            )
            decision = ArchiveOperationDecision(
                status="accepted",
                operation="updated_archive",
                project_name="my-vps-blog",
                confidence="high",
                reason="Same project and same setup archive.",
                abstract="Adds troubleshooting details for Nginx HTTPS.",
                target_archive_path="archives/nginx-https-setup.md",
                merged_title="Nginx HTTPS setup",
                merged_content="# Nginx HTTPS setup\n\nOriginal setup plus troubleshooting.",
                change_summary="Added troubleshooting details.",
            )

            updated = update_archive_in_project(
                vault_dir=vault,
                project_name="my-vps-blog",
                request=update_request,
                decision=decision,
            )

            self.assertEqual(created.path, updated.path)
            updated_text = updated.path.read_text(encoding="utf-8")
            self.assertNotEqual(original_text, updated_text)
            self.assertIn(f'created_at: "{original_created_at}"', updated_text)
            self.assertIn('modified_at: "', updated_text)
            self.assertIn("# Nginx HTTPS setup\n\nOriginal setup plus troubleshooting.", updated_text)

            index_text = (vault / "my-vps-blog" / "index.md").read_text(encoding="utf-8")
            self.assertIn("updated_archive", index_text)
            self.assertIn("Added troubleshooting details.", index_text)
            self.assertEqual(2, index_text.count("archives/nginx-https-setup.md"))


if __name__ == "__main__":
    unittest.main()
