"""Tests for the hybrid ensemble prediction engine."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from app.core.hybrid_inference import predict_hybrid


class TestHybridInference(unittest.TestCase):
    """Test suite for hybrid ensemble prediction and fallback logic."""

    def setUp(self) -> None:
        self.target_group = "S1"
        self.from_date = "2026-06-09"
        self.to_date = "2026-06-11"  # 3 days (Tue, Wed, Thu)
        
        self.tft_mock_response = {
            "target_group": self.target_group,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "model_version": "deep-s1-v1",
            "model_type": "deep_tft",
            "count": 3,
            "steps": [
                {
                    "date": "2026-06-09",
                    "event_day": 1,
                    "predictions": {
                        "S1 +2": {"p10": 100.0, "p50": 110.0, "p90": 120.0},
                        "S1 +4": {"p10": 120.0, "p50": 130.0, "p90": 140.0},
                        "S1 +6": {"p10": 140.0, "p50": 150.0, "p90": 160.0},
                    }
                },
                {
                    "date": "2026-06-10",
                    "event_day": 2,
                    "predictions": {
                        "S1 +2": {"p10": 105.0, "p50": 115.0, "p90": 125.0},
                        "S1 +4": {"p10": 125.0, "p50": 135.0, "p90": 145.0},
                        "S1 +6": {"p10": 145.0, "p50": 155.0, "p90": 165.0},
                    }
                },
                {
                    "date": "2026-06-11",
                    "event_day": 3,
                    "predictions": {
                        "S1 +2": {"p10": 110.0, "p50": 120.0, "p90": 130.0},
                        "S1 +4": {"p10": 130.0, "p50": 140.0, "p90": 150.0},
                        "S1 +6": {"p10": 150.0, "p50": 160.0, "p90": 170.0},
                    }
                }
            ]
        }

        self.lgbm_mock_responses = {
            "S1 +2": {
                "target": "S1 +2",
                "from_date": self.from_date,
                "to_date": self.to_date,
                "model_version": "lgbm-s1-2-v1",
                "model_type": "lightgbm",
                "count": 3,
                "predictions": [
                    {"date": "2026-06-09", "prediction": 108.0, "interval": {"p10": 98.0, "p50": 108.0, "p90": 118.0}},
                    {"date": "2026-06-10", "prediction": 113.0, "interval": {"p10": 103.0, "p50": 113.0, "p90": 123.0}},
                    {"date": "2026-06-11", "prediction": 118.0, "interval": {"p10": 108.0, "p50": 118.0, "p90": 128.0}},
                ]
            },
            "S1 +4": {
                "target": "S1 +4",
                "from_date": self.from_date,
                "to_date": self.to_date,
                "model_version": "lgbm-s1-4-v1",
                "model_type": "lightgbm",
                "count": 3,
                "predictions": [
                    {"date": "2026-06-09", "prediction": 128.0, "interval": {"p10": 118.0, "p50": 128.0, "p90": 138.0}},
                    {"date": "2026-06-10", "prediction": 133.0, "interval": {"p10": 123.0, "p50": 133.0, "p90": 143.0}},
                    {"date": "2026-06-11", "prediction": 138.0, "interval": {"p10": 128.0, "p50": 138.0, "p90": 148.0}},
                ]
            },
            "S1 +6": {
                "target": "S1 +6",
                "from_date": self.from_date,
                "to_date": self.to_date,
                "model_version": "lgbm-s1-6-v1",
                "model_type": "lightgbm",
                "count": 3,
                "predictions": [
                    {"date": "2026-06-09", "prediction": 148.0, "interval": {"p10": 138.0, "p50": 148.0, "p90": 158.0}},
                    {"date": "2026-06-10", "prediction": 153.0, "interval": {"p10": 143.0, "p50": 153.0, "p90": 163.0}},
                    {"date": "2026-06-11", "prediction": 158.0, "interval": {"p10": 148.0, "p50": 158.0, "p90": 168.0}},
                ]
            }
        }

    @patch("app.core.hybrid_inference._cached_read_csv")
    @patch("app.core.hybrid_inference._discover_target_groups")
    @patch("app.core.hybrid_inference.predict_group_future_cached")
    @patch("app.core.hybrid_inference.predict_for_date_range")
    def test_predict_hybrid_success(
        self,
        mock_lgbm_predict,
        mock_tft_predict,
        mock_discover_groups,
        mock_cached_read_csv
    ) -> None:
        """Test successful hybrid blending."""
        mock_cached_read_csv.return_value = pd.DataFrame(columns=["S1 +2", "S1 +4", "S1 +6"])
        mock_discover_groups.return_value = {self.target_group: ["S1 +2", "S1 +4", "S1 +6"]}
        
        mock_tft_predict.return_value = self.tft_mock_response
        mock_lgbm_predict.side_effect = lambda tier, fd, td: self.lgbm_mock_responses[tier]

        # Call predict_hybrid with w_tft=0.6
        res = predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=0.6)

        assert res["target_group"] == self.target_group
        assert res["model_type"] == "hybrid_ensemble"
        assert res["blending_status"] == "blended"
        assert res["w_tft"] == 0.6
        assert res["count"] == 3
        
        # Verify blending math for first step:
        # TFT +2 p50: 110.0, LGBM +2 p50: 108.0 -> 0.6 * 110.0 + 0.4 * 108.0 = 66.0 + 43.2 = 109.2
        first_step = res["steps"][0]
        assert first_step["date"] == "2026-06-09"
        assert first_step["event_day"] == 1
        assert first_step["predictions"]["S1 +2"]["p50"] == 109.2
        
        # Verify monotonicity: p10 <= p50 <= p90
        for step in res["steps"]:
            for tier in ["S1 +2", "S1 +4", "S1 +6"]:
                preds = step["predictions"][tier]
                assert preds["p10"] <= preds["p50"] <= preds["p90"]
            
            # Verify tier monotonicity: S1 +2 <= S1 +4 <= S1 +6
            assert step["predictions"]["S1 +2"]["p50"] <= step["predictions"]["S1 +4"]["p50"]
            assert step["predictions"]["S1 +4"]["p50"] <= step["predictions"]["S1 +6"]["p50"]

    @patch("app.core.hybrid_inference._cached_read_csv")
    @patch("app.core.hybrid_inference._discover_target_groups")
    @patch("app.core.hybrid_inference.predict_group_future_cached")
    @patch("app.core.hybrid_inference.predict_for_date_range")
    def test_predict_hybrid_fallback_tft_only(
        self,
        mock_lgbm_predict,
        mock_tft_predict,
        mock_discover_groups,
        mock_cached_read_csv
    ) -> None:
        """Test fallback to TFT only when LightGBM model fails."""
        mock_cached_read_csv.return_value = pd.DataFrame(columns=["S1 +2", "S1 +4", "S1 +6"])
        mock_discover_groups.return_value = {self.target_group: ["S1 +2", "S1 +4", "S1 +6"]}
        
        mock_tft_predict.return_value = self.tft_mock_response
        mock_lgbm_predict.side_effect = Exception("LightGBM missing")

        res = predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=0.6)

        assert res["model_type"] == "deep_tft"
        assert res["blending_status"] == "tft_only"
        assert res["w_tft"] == 1.0

    @patch("app.core.hybrid_inference._cached_read_csv")
    @patch("app.core.hybrid_inference._discover_target_groups")
    @patch("app.core.hybrid_inference.predict_group_future_cached")
    @patch("app.core.hybrid_inference.predict_for_date_range")
    def test_predict_hybrid_fallback_lgbm_only(
        self,
        mock_lgbm_predict,
        mock_tft_predict,
        mock_discover_groups,
        mock_cached_read_csv
    ) -> None:
        """Test fallback to LightGBM only when TFT model fails."""
        mock_cached_read_csv.return_value = pd.DataFrame(columns=["S1 +2", "S1 +4", "S1 +6"])
        mock_discover_groups.return_value = {self.target_group: ["S1 +2", "S1 +4", "S1 +6"]}
        
        mock_tft_predict.side_effect = Exception("TFT model load error")
        mock_lgbm_predict.side_effect = lambda tier, fd, td: self.lgbm_mock_responses[tier]

        res = predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=0.6)

        assert res["model_type"] == "lightgbm"
        assert res["blending_status"] == "lgbm_only"
        assert res["w_tft"] == 0.0
        assert res["steps"][0]["predictions"]["S1 +2"]["p50"] == 108.0

    @patch("app.core.hybrid_inference._cached_read_csv")
    @patch("app.core.hybrid_inference._discover_target_groups")
    @patch("app.core.hybrid_inference.predict_group_future_cached")
    @patch("app.core.hybrid_inference.predict_for_date_range")
    def test_predict_hybrid_both_fail(
        self,
        mock_lgbm_predict,
        mock_tft_predict,
        mock_discover_groups,
        mock_cached_read_csv
    ) -> None:
        """Test ValueError when both models fail."""
        mock_cached_read_csv.return_value = pd.DataFrame(columns=["S1 +2", "S1 +4", "S1 +6"])
        mock_discover_groups.return_value = {self.target_group: ["S1 +2", "S1 +4", "S1 +6"]}
        
        mock_tft_predict.side_effect = Exception("TFT fail")
        mock_lgbm_predict.side_effect = Exception("LGBM fail")

        with self.assertRaises(ValueError):
            predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=0.6)

    def test_predict_hybrid_invalid_w_tft(self) -> None:
        """Test invalid w_tft values raise ValueError."""
        with self.assertRaises(ValueError):
            predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=1.1)
        with self.assertRaises(ValueError):
            predict_hybrid(self.target_group, self.from_date, self.to_date, w_tft=-0.1)
