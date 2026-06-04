import unittest

import numpy as np
import pandas as pd

from app.core.features import FEATURES_VERSION, build_feature_frame, normalize_profile


def _sample_df(rows: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    values = np.linspace(100, 200, rows) + np.sin(np.arange(rows) / 7) * 5
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "day": dates.day,
            "weekday_num": dates.weekday,
            "quarter": ((dates.month - 1) // 3 + 1).astype(int),
            "is_month_start": (dates.day == 1).astype(int),
            "is_month_end": dates.is_month_end.astype(int),
            "target_col": values,
        }
    )


class FeatureFrameTests(unittest.TestCase):
    def test_features_version_is_set(self) -> None:
        self.assertTrue(FEATURES_VERSION)

    def test_full_alias_maps_to_step3(self) -> None:
        self.assertEqual(normalize_profile("full"), "step3")

    def test_step3_has_extended_columns(self) -> None:
        frame = build_feature_frame(_sample_df(), "target_col", profile="step3")
        for col in (
            "rolling_std_7",
            "weekday_seasonal_mean",
            "is_holiday_jp",
            "is_long_weekend_window",
        ):
            self.assertIn(col, frame.columns)

    def test_step1_is_subset_of_step3_columns(self) -> None:
        step1 = build_feature_frame(_sample_df(), "target_col", profile="step1")
        step3 = build_feature_frame(_sample_df(), "target_col", profile="step3")
        self.assertNotIn("is_holiday_jp", step1.columns)
        self.assertIn("is_holiday_jp", step3.columns)
        self.assertGreater(len(step3.columns), len(step1.columns))

    def test_lag_1_uses_previous_day_only(self) -> None:
        df = _sample_df(40)
        frame = build_feature_frame(df, "target_col", profile="step1")
        idx = 10
        date = df["date"].iloc[idx]
        row = frame[frame["date"] == date].iloc[0]
        self.assertAlmostEqual(row["lag_1"], df["target_col"].iloc[idx - 1])

    def test_future_row_target_nan_does_not_fill_same_day_lag(self) -> None:
        df = _sample_df(150)
        future_date = "2024-05-20"
        ts = pd.Timestamp(future_date)
        extended = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "date": future_date,
                            "year": ts.year,
                            "month": ts.month,
                            "day": ts.day,
                            "weekday_num": ts.weekday(),
                            "quarter": (ts.month - 1) // 3 + 1,
                            "is_month_start": int(ts.day == 1),
                            "is_month_end": 0,
                            "target_col": np.nan,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        frame = build_feature_frame(extended, "target_col", profile="step1")
        row = frame[frame["date"] == future_date].iloc[0]
        self.assertFalse(np.isnan(row["lag_1"]))
        self.assertNotEqual(row["lag_1"], row["y"])


if __name__ == "__main__":
    unittest.main()
