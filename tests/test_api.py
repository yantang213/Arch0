import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from arch0.app import create_app
from arch0.config import Settings
from arch0.decision_engine import StaticDecisionEngine
from arch0.models import ArchiveDecision, ArchiveOperationDecision


class StaticOperationEngine:
    def __init__(self, decisions: list[ArchiveOperationDecision]):
        self.decisions = decisions
        self.calls = 0

    def decide_operation(self, request, context):
        decision = self.decisions[self.calls]
        self.calls += 1
        return decision


class ApiTests(unittest.TestCase):
    def make_settings(self, vault: Path, *, token: str | None = None, host: str = "127.0.0.1") -> Settings:
        return Settings(
            vault_dir=vault,
            bind_host=host,
            bind_port=8000,
            api_token=token,
            llm_api_key=None,
            llm_base_url="https://example.invalid/v1",
            llm_model="test-model",
        )

    def make_payload(self) -> dict:
        return {
            "cmd_type": "insert",
            "instruction": "Archive this completed VPS setup summary.",
            "archive_title": "Nginx HTTPS setup",
            "archive_content": "# Nginx HTTPS setup\n\n" + "This is a completed work summary. " * 8,
            "send_from_who": "remote-agent:agent-b@vps-prod",
        }

    def test_healthz(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(
                settings=self.make_settings(Path(tmp) / "arch-vault"),
                decision_engine=StaticDecisionEngine(
                    ArchiveDecision(status="needs_review", project_name=None, confidence="low", reason="test")
                ),
            )
            client = TestClient(app)
            self.assertEqual({"status": "ok"}, client.get("/healthz").json())

    def test_valid_submission_archives_and_recalls(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            decision = ArchiveDecision(
                status="accepted",
                project_name="my-vps-blog",
                confidence="high",
                reason="Matches project.",
                abstract="Documents Nginx HTTPS setup.",
            )
            engine = StaticDecisionEngine(decision)
            client = TestClient(create_app(settings=self.make_settings(vault), decision_engine=engine))

            response = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, response.status_code, response.text)
            data = response.json()
            self.assertEqual("accepted", data["status"])
            self.assertEqual("created_archive", data["operation"])
            self.assertEqual("my-vps-blog", data["project_name"])
            self.assertEqual("Documents Nginx HTTPS setup.", data["decision_detail"]["abstract"])
            self.assertTrue(data["git_committed"])
            self.assertIsNotNone(data["git_commit"])
            self.assertTrue((vault / "my-vps-blog" / "archives" / "nginx-https-setup.md").exists())
            self.assertEqual(1, engine.calls)

            recall = client.get("/v0.1/recall/my-vps-blog")
            self.assertEqual(200, recall.status_code, recall.text)
            recall_data = recall.json()
            self.assertEqual("my-vps-blog", recall_data["project_name"])
            self.assertEqual(1, len(recall_data["documents"]))
            self.assertEqual("Documents Nginx HTTPS setup.", recall_data["documents"][0]["abstract"])
            self.assertIn("# Nginx HTTPS setup", recall_data["documents"][0]["markdown"])

    def test_needs_review_stores_in_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            engine = StaticDecisionEngine(
                ArchiveDecision(
                    status="needs_review",
                    project_name=None,
                    confidence="low",
                    reason="Ambiguous target.",
                    abstract="Could be useful.",
                )
            )
            client = TestClient(create_app(settings=self.make_settings(vault), decision_engine=engine))
            response = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, response.status_code, response.text)
            data = response.json()
            self.assertEqual("needs_review", data["status"])
            self.assertEqual("needs_review", data["operation"])
            self.assertIsNone(data["project_name"])
            self.assertTrue((vault / "inbox" / "needs-review" / "nginx-https-setup.md").exists())

    def test_operation_engine_can_update_existing_archive_with_git_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            engine = StaticOperationEngine(
                [
                    ArchiveOperationDecision(
                        status="accepted",
                        operation="created_archive",
                        project_name="my-vps-blog",
                        confidence="high",
                        reason="New project memory.",
                        abstract="Documents Nginx HTTPS setup.",
                    ),
                    ArchiveOperationDecision(
                        status="accepted",
                        operation="updated_archive",
                        project_name="my-vps-blog",
                        confidence="high",
                        reason="Updates the same setup document.",
                        abstract="Adds troubleshooting details.",
                        target_archive_path="archives/nginx-https-setup.md",
                        merged_title="Nginx HTTPS setup",
                        merged_content="# Nginx HTTPS setup\n\nSetup plus troubleshooting details.",
                        change_summary="Added troubleshooting details.",
                    ),
                ]
            )
            client = TestClient(create_app(settings=self.make_settings(vault), decision_engine=engine))

            created = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, created.status_code, created.text)
            updated = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, updated.status_code, updated.text)

            created_data = created.json()
            updated_data = updated.json()
            self.assertEqual("created_archive", created_data["operation"])
            self.assertEqual("updated_archive", updated_data["operation"])
            self.assertEqual(created_data["stored_path"], updated_data["stored_path"])
            self.assertTrue(updated_data["git_committed"])
            self.assertIsNotNone(updated_data["git_commit"])
            self.assertEqual("Added troubleshooting details.", updated_data["decision_detail"]["change_summary"])

            archive_text = (vault / "my-vps-blog" / "archives" / "nginx-https-setup.md").read_text(encoding="utf-8")
            self.assertIn("Setup plus troubleshooting details.", archive_text)
            index_text = (vault / "my-vps-blog" / "index.md").read_text(encoding="utf-8")
            self.assertIn("created_archive", index_text)
            self.assertIn("updated_archive", index_text)

    def test_dirty_vault_forces_needs_review_before_operation_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            vault.mkdir(parents=True)
            (vault / "manual-note.md").write_text("uncommitted manual change\n", encoding="utf-8")
            engine = StaticOperationEngine(
                [
                    ArchiveOperationDecision(
                        status="accepted",
                        operation="created_archive",
                        project_name="my-vps-blog",
                        confidence="high",
                        reason="Should not write automatically.",
                        abstract="Documents Nginx HTTPS setup.",
                    )
                ]
            )
            client = TestClient(create_app(settings=self.make_settings(vault), decision_engine=engine))

            response = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, response.status_code, response.text)
            data = response.json()
            self.assertEqual("needs_review", data["status"])
            self.assertEqual("needs_review", data["operation"])
            self.assertEqual(0, engine.calls)
            self.assertIn("Vault has uncommitted changes.", data["warnings"])
            self.assertTrue((vault / "inbox" / "needs-review" / "nginx-https-setup.md").exists())

    def test_secret_rejected_before_decision_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            engine = StaticDecisionEngine(
                ArchiveDecision(status="accepted", project_name="bad", confidence="high", reason="Should not call")
            )
            client = TestClient(create_app(settings=self.make_settings(vault), decision_engine=engine))
            payload = self.make_payload()
            payload["archive_content"] = (
                "# Secret\n\n"
                + "This otherwise looks like a long enough work summary. " * 4
                + "\n-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n"
            )
            response = client.post("/v0.1/archives", json=payload)
            self.assertEqual(200, response.status_code, response.text)
            data = response.json()
            self.assertEqual("rejected", data["status"])
            self.assertEqual("rejected", data["operation"])
            self.assertIsNone(data["stored_path"])
            self.assertTrue(data["git_committed"])
            self.assertIsNotNone(data["git_commit"])
            self.assertEqual(0, engine.calls)
            archive_files = list(vault.glob("**/*.md"))
            self.assertEqual([vault / "audit" / "audit-log.md"], archive_files)

    def test_auth_enforced_when_token_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            client = TestClient(
                create_app(
                    settings=self.make_settings(vault, token="secret-token"),
                    decision_engine=StaticDecisionEngine(
                        ArchiveDecision(status="needs_review", project_name=None, confidence="low", reason="test")
                    ),
                )
            )
            self.assertEqual(401, client.post("/v0.1/archives", json=self.make_payload()).status_code)
            ok = client.post(
                "/v0.1/archives",
                json=self.make_payload(),
                headers={"Authorization": "Bearer secret-token"},
            )
            self.assertEqual(200, ok.status_code, ok.text)

    def test_auth_not_required_on_non_loopback_host_when_token_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            client = TestClient(
                create_app(
                    settings=self.make_settings(vault, host="0.0.0.0"),
                    decision_engine=StaticDecisionEngine(
                        ArchiveDecision(status="needs_review", project_name=None, confidence="low", reason="test")
                    ),
                )
            )
            response = client.post("/v0.1/archives", json=self.make_payload())
            self.assertEqual(200, response.status_code, response.text)

    def test_invalid_cmd_type_returns_structured_400(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "arch-vault"
            client = TestClient(
                create_app(
                    settings=self.make_settings(vault),
                    decision_engine=StaticDecisionEngine(
                        ArchiveDecision(status="needs_review", project_name=None, confidence="low", reason="test")
                    ),
                )
            )
            payload = self.make_payload()
            payload["cmd_type"] = "update"
            response = client.post("/v0.1/archives", json=payload)
            self.assertEqual(400, response.status_code, response.text)
            self.assertEqual("invalid_cmd_type", response.json()["detail"]["code"])


if __name__ == "__main__":
    unittest.main()
