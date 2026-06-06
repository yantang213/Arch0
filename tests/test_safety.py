import unittest

from arch0.safety import scan_for_secrets


class SafetyTests(unittest.TestCase):
    def test_detects_private_key_marker(self):
        findings = scan_for_secrets("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----")
        self.assertTrue(any(f.code == "private_key" for f in findings))

    def test_detects_openai_style_key(self):
        findings = scan_for_secrets("token: sk-abcdefghijklmnopqrstuvwxyz123456")
        self.assertTrue(any(f.code == "openai_key" for f in findings))

    def test_does_not_flag_secret_manager_reference(self):
        findings = scan_for_secrets("The database password is stored in 1Password under VPS/prod-db.")
        self.assertEqual([], findings)


if __name__ == "__main__":
    unittest.main()

