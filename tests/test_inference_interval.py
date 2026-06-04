import unittest

from app.core.inference import _prediction_interval


class PredictionIntervalTests(unittest.TestCase):
    def test_cv_residual_calibration(self) -> None:
        artifact = {
            "interval_calibration": {
                "method": "cv_residual_quantile",
                "p10_offset": -5.0,
                "p90_offset": 8.0,
            }
        }
        p10, p90 = _prediction_interval(100.0, artifact)
        self.assertEqual(p10, 95.0)
        self.assertEqual(p90, 108.0)

    def test_legacy_rmse_fallback(self) -> None:
        artifact = {"metrics_train": {"rmse": 10.0}}
        p10, p90 = _prediction_interval(100.0, artifact)
        self.assertAlmostEqual(p10, 100.0 - 12.8)
        self.assertAlmostEqual(p90, 100.0 + 12.8)


if __name__ == "__main__":
    unittest.main()
