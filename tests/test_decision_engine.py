import unittest

from arch0.decision_engine import DecisionEngineError, parse_decision


class DecisionEngineTests(unittest.TestCase):
    def test_parse_valid_accepted_decision(self):
        decision = parse_decision(
            """
            {
              "status": "accepted",
              "project_name": "my-vps-blog",
              "confidence": "high",
              "reason": "Matches an existing project.",
              "abstract": "Documents a completed Nginx HTTPS setup."
            }
            """
        )
        self.assertEqual("accepted", decision.status)
        self.assertEqual("my-vps-blog", decision.project_name)
        self.assertEqual("high", decision.confidence)

    def test_parse_needs_review_drops_project_name(self):
        decision = parse_decision(
            """
            {
              "status": "needs_review",
              "project_name": "some-project",
              "confidence": "low",
              "reason": "Ambiguous target.",
              "abstract": "Potentially useful archive."
            }
            """
        )
        self.assertEqual("needs_review", decision.status)
        self.assertIsNone(decision.project_name)

    def test_rejects_invalid_project_name(self):
        with self.assertRaises(DecisionEngineError):
            parse_decision(
                """
                {
                  "status": "accepted",
                  "project_name": "../bad",
                  "confidence": "high",
                  "reason": "Bad path.",
                  "abstract": "Bad."
                }
                """
            )


if __name__ == "__main__":
    unittest.main()

