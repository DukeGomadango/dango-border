import unittest

from app.core.inference import predict_for_date_range
from app.core.settings import MAX_PREDICTION_RANGE_DAYS


class PredictionRangeValidationTests(unittest.TestCase):
    def test_rejects_inverted_dates(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            predict_for_date_range("S1 +6", "2026-02-01", "2026-01-01")
        self.assertIn("to_date", str(ctx.exception))

    def test_rejects_long_ranges(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            predict_for_date_range("S1 +6", "2024-01-01", "2024-06-01")
        self.assertIn(str(MAX_PREDICTION_RANGE_DAYS), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
