import tempfile
import unittest
from pathlib import Path

from arch0.config import Settings
from arch0.validation import ValidationError, validate_archive_request_shape, validate_project_name


class ValidationTests(unittest.TestCase):
    def settings(self) -> Settings:
        return Settings(
            vault_dir=Path(tempfile.gettempdir()) / "arch0-test",
            bind_host="127.0.0.1",
            bind_port=8000,
            api_token=None,
            llm_api_key=None,
            llm_base_url="https://example.invalid/v1",
            llm_model="test-model",
        )

    def test_valid_project_name_can_be_human_readable(self):
        self.assertEqual("My VPS Blog", validate_project_name("My VPS Blog"))

    def test_invalid_project_name_rejects_traversal(self):
        with self.assertRaises(ValidationError):
            validate_project_name("../bad")

    def test_invalid_project_name_rejects_reserved(self):
        with self.assertRaises(ValidationError):
            validate_project_name("inbox")

    def test_archive_content_too_short(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_archive_request_shape(
                archive_title="Title",
                archive_content="too short",
                send_from_who="remote-agent",
                settings=self.settings(),
            )
        self.assertEqual("archive_content_too_short", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()

