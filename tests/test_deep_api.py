"""Tests for the Deep Learning API endpoints."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.api.deep import deep_predict
from app.models.schemas import DeepGroupForecastResponse


class TestDeepAPI(unittest.TestCase):
    """Test suite for deep predictions endpoint handler behavior."""

    @patch("app.api.deep.predict_hybrid")
    def test_deep_predict_hybrid_default(self, mock_predict_hybrid) -> None:
        """Endpoint should default to use_hybrid=True and w_tft=0.6."""
        mock_predict_hybrid.return_value = {
            "target_group": "S1",
            "from_date": "2026-06-09",
            "to_date": "2026-06-11",
            "model_version": "hybrid-s1",
            "model_type": "hybrid_ensemble",
            "blending_status": "blended",
            "w_tft": 0.6,
            "count": 1,
            "steps": [
                {
                    "date": "2026-06-09",
                    "event_day": 1,
                    "predictions": {
                        "S1 +2": {"p10": 100.0, "p50": 110.0, "p90": 120.0},
                        "S1 +4": {"p10": 120.0, "p50": 130.0, "p90": 140.0},
                        "S1 +6": {"p10": 140.0, "p50": 150.0, "p90": 160.0},
                    }
                }
            ]
        }

        # Call the endpoint handler function directly
        res = deep_predict(
            target_group="S1",
            from_date="2026-06-09",
            to_date="2026-06-11"
        )

        assert isinstance(res, DeepGroupForecastResponse)
        assert res.target_group == "S1"
        assert res.model_type == "hybrid_ensemble"
        assert res.blending_status == "blended"
        assert res.w_tft == 0.6
        
        # Verify call arguments
        mock_predict_hybrid.assert_called_once_with(
            target_group="S1",
            from_date="2026-06-09",
            to_date="2026-06-11",
            w_tft=0.6
        )

    @patch("app.api.deep.predict_group_future")
    def test_deep_predict_tft_only(self, mock_predict_group_future) -> None:
        """Endpoint should call predict_group_future if use_hybrid=False."""
        mock_predict_group_future.return_value = {
            "target_group": "S1",
            "from_date": "2026-06-09",
            "to_date": "2026-06-11",
            "model_version": "deep-s1-v1",
            "model_type": "deep_tft",
            "count": 1,
            "steps": [
                {
                    "date": "2026-06-09",
                    "event_day": 1,
                    "predictions": {
                        "S1 +2": {"p10": 100.0, "p50": 110.0, "p90": 120.0},
                        "S1 +4": {"p10": 120.0, "p50": 130.0, "p90": 140.0},
                        "S1 +6": {"p10": 140.0, "p50": 150.0, "p90": 160.0},
                    }
                }
            ]
        }

        # Call direct with use_hybrid=False
        res = deep_predict(
            target_group="S1",
            from_date="2026-06-09",
            to_date="2026-06-11",
            use_hybrid=False
        )

        assert isinstance(res, DeepGroupForecastResponse)
        assert res.target_group == "S1"
        assert res.model_type == "deep_tft"
        assert res.blending_status is None
        assert res.w_tft is None
        
        mock_predict_group_future.assert_called_once_with(
            target_group="S1",
            from_date="2026-06-09",
            to_date="2026-06-11"
        )
