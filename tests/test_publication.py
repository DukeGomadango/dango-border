import unittest
from unittest.mock import patch

from app.core.publication import (
    PUBLICATION_GOAL,
    evaluate_publication_eligibility,
    get_publication_plan,
    promote_target,
)


class PublicationPlanTests(unittest.TestCase):
    @patch("app.core.publication._load_targets")
    def test_plan_counts_published(self, load_targets) -> None:
        load_targets.return_value = [
            {"target": "A", "status": "ready", "publish": True},
            {"target": "B", "status": "beta", "publish": True},
            {"target": "C", "status": "beta", "publish": False},
            {"target": "D", "status": "blocked", "publish": False},
        ]
        with patch("app.core.publication.list_publication_candidates", return_value=[]):
            plan = get_publication_plan()
        self.assertEqual(plan["goal"], PUBLICATION_GOAL)
        self.assertEqual(plan["published_count"], 2)
        self.assertEqual(plan["remaining_slots"], PUBLICATION_GOAL - 2)

    @patch("app.core.publication._find_target")
    @patch("app.core.publication.get_current_model")
    def test_eligible_beta_candidate(self, get_current_model, find_target) -> None:
        find_target.return_value = {"target": "S2 +4", "status": "beta", "publish": False}
        get_current_model.return_value = {
            "evaluation": {"adopted": True, "improvement_rate": 0.15, "cv_mae": 10.0},
        }
        item = evaluate_publication_eligibility("S2 +4")
        self.assertTrue(item.eligible)
        self.assertEqual(item.reasons, [])

    @patch("app.core.publication.get_publication_plan")
    @patch("app.core.publication._set_publish")
    @patch("app.core.publication.evaluate_publication_eligibility")
    def test_promote_respects_goal(self, evaluate, set_publish, plan) -> None:
        evaluate.return_value = unittest.mock.Mock(
            publish=False,
            eligible=True,
            reasons=[],
        )
        plan.return_value = {"remaining_slots": 0}
        result = promote_target("S2 +4", reason="test")
        self.assertFalse(result.promoted)
        set_publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
