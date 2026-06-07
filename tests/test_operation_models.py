import unittest

from pydantic import ValidationError

from arch0.models import ArchiveOperationDecision


class OperationModelTests(unittest.TestCase):
    def test_created_archive_decision(self):
        decision = ArchiveOperationDecision(
            status="accepted",
            operation="created_archive",
            project_name="my-vps-blog",
            confidence="high",
            reason="New useful project memory.",
            abstract="Documents Nginx HTTPS setup.",
        )
        self.assertEqual("created_archive", decision.operation)

    def test_updated_archive_requires_target_and_change_summary(self):
        with self.assertRaises(ValidationError):
            ArchiveOperationDecision(
                status="accepted",
                operation="updated_archive",
                project_name="my-vps-blog",
                confidence="high",
                reason="Updates an existing archive.",
                abstract="Updated setup notes.",
                merged_content="# Updated\n\nContent",
            )

        with self.assertRaises(ValidationError):
            ArchiveOperationDecision(
                status="accepted",
                operation="updated_archive",
                project_name="my-vps-blog",
                confidence="high",
                reason="Updates an existing archive.",
                abstract="Updated setup notes.",
                target_archive_path="archives/nginx-https-setup.md",
                merged_content="# Updated\n\nContent",
            )

    def test_updated_archive_requires_high_confidence(self):
        with self.assertRaises(ValidationError):
            ArchiveOperationDecision(
                status="accepted",
                operation="updated_archive",
                project_name="my-vps-blog",
                confidence="medium",
                reason="Maybe updates an existing archive.",
                abstract="Updated setup notes.",
                target_archive_path="archives/nginx-https-setup.md",
                merged_content="# Updated\n\nContent",
                change_summary="Added troubleshooting details.",
            )

    def test_updated_archive_rejects_unsafe_target_path(self):
        for bad_path in ["/tmp/outside.md", "../outside.md", "archives/../../outside.md"]:
            with self.subTest(bad_path=bad_path):
                with self.assertRaises(ValidationError):
                    ArchiveOperationDecision(
                        status="accepted",
                        operation="updated_archive",
                        project_name="my-vps-blog",
                        confidence="high",
                        reason="Updates an existing archive.",
                        abstract="Updated setup notes.",
                        target_archive_path=bad_path,
                        merged_content="# Updated\n\nContent",
                        change_summary="Added troubleshooting details.",
                    )


if __name__ == "__main__":
    unittest.main()
