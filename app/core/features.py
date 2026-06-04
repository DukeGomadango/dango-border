import holidays
import numpy as np
import pandas as pd

FEATURES_VERSION = "4.0.0"

# step1: calendar + short lags
# step2: + long lags, rolling, weekday seasonal
# step3: + JP holidays and long-weekend window
# sparse: minimal set for low-coverage targets (backward compatible)
# full: alias of step3
PROFILE_ALIASES = {"full": "step3"}
STEP_PROFILES = ("step1", "step2", "step3")


_HOLIDAY_CACHE: dict[int, set] = {}


def _get_japan_holidays_for_years(years) -> set:
    import holidays
    all_holidays = set()
    for year in years:
        if year not in _HOLIDAY_CACHE:
            _HOLIDAY_CACHE[year] = set(holidays.Japan(years=year).keys())
        all_holidays.update(_HOLIDAY_CACHE[year])
    return all_holidays


def normalize_profile(profile: str) -> str:
    normalized = PROFILE_ALIASES.get(profile, profile)
    allowed = set(STEP_PROFILES) | {"sparse"}
    if normalized not in allowed:
        raise ValueError(
            f"Unknown feature profile '{profile}'. "
            f"Use one of: {', '.join(sorted(allowed | set(PROFILE_ALIASES)))}, full."
        )
    return normalized


def build_feature_frame(df: pd.DataFrame, target: str, profile: str = "step3", drop_nans: bool = True) -> pd.DataFrame:
    profile = normalize_profile(profile)
    s = pd.to_numeric(df[target], errors="coerce")
    features = pd.DataFrame(index=df.index)
    features["date"] = df["date"]
    features["year"] = pd.to_numeric(df["year"], errors="coerce")
    features["month"] = pd.to_numeric(df["month"], errors="coerce")
    features["day"] = pd.to_numeric(df["day"], errors="coerce")
    features["weekday_num"] = pd.to_numeric(df["weekday_num"], errors="coerce")
    features["quarter"] = pd.to_numeric(df["quarter"], errors="coerce")
    features["is_month_start"] = pd.to_numeric(df["is_month_start"], errors="coerce")
    features["is_month_end"] = pd.to_numeric(df["is_month_end"], errors="coerce")

    past = s.shift(1)
    features["lag_1"] = past
    features["lag_7"] = s.shift(7)

    if profile in ("step2", "step3"):
        features["lag_14"] = s.shift(14)
        features["lag_28"] = s.shift(28)
        features["rolling_mean_7"] = past.rolling(7).mean()
        features["rolling_mean_28"] = past.rolling(28).mean()
        features["rolling_std_7"] = past.rolling(7).std()
        features["rolling_std_28"] = past.rolling(28).std()
        features["weekday_seasonal_mean"] = _weekday_seasonal_mean(features["weekday_num"], past)
    elif profile == "sparse":
        features["rolling_mean_7"] = past.rolling(7).mean()

    if profile == "step3":
        _add_holiday_features(features)
        _add_long_weekend_window(features)
        _add_large_holiday_clusters(features)
        _add_platform_activity_features(features, df, target)

    # IRIAM event cycle features (available for all profiles: purely calendar-based)
    _add_event_cycle_features(features)

    # Gap decay features (step2+ only: requires target series context)
    if profile in ("step2", "step3"):
        _add_gap_decay_features(features, s)

    features["y"] = s
    feature_cols = [c for c in features.columns if c not in ("y", "date")]
    if drop_nans:
        return features.dropna(subset=feature_cols).reset_index(drop=True)
    return features


def feature_matrix(feature_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    x = feature_df.drop(columns=["y", "date"])
    y = feature_df["y"]
    return x, y


def _weekday_seasonal_mean(weekday_num: pd.Series, past_values: pd.Series) -> pd.Series:
    frame = pd.DataFrame({"weekday_num": weekday_num, "past": past_values})
    return frame.groupby("weekday_num", sort=False)["past"].transform(
        lambda values: values.expanding(min_periods=1).mean()
    )


def _add_holiday_features(features: pd.DataFrame) -> None:
    dates = pd.to_datetime(features["date"])
    if dates.empty:
        return
    years = range(int(dates.dt.year.min()), int(dates.dt.year.max()) + 1)
    holiday_set = _get_japan_holidays_for_years(years)
    is_holiday = dates.dt.date.map(lambda d: 1 if d in holiday_set else 0).astype(int)
    features["is_holiday_jp"] = is_holiday
    features["is_day_before_holiday"] = is_holiday.shift(-1).fillna(0).astype(int)
    features["is_day_after_holiday"] = is_holiday.shift(1).fillna(0).astype(int)


def _add_long_weekend_window(features: pd.DataFrame) -> None:
    """Flag days within one day of a 3+ consecutive off-day run (weekend or JP holiday)."""
    dates = pd.to_datetime(features["date"])
    if dates.empty:
        features["is_long_weekend_window"] = 0
        return

    years = range(int(dates.dt.year.min()), int(dates.dt.year.max()) + 1)
    holiday_set = _get_japan_holidays_for_years(years)
    is_holiday = dates.dt.date.map(lambda d: 1 if d in holiday_set else 0).to_numpy(dtype=int)
    is_weekend = dates.dt.weekday.to_numpy(dtype=int) >= 5
    is_off = np.where((is_holiday == 1) | is_weekend, 1, 0)

    window = np.zeros(len(is_off), dtype=int)
    run_start = None
    for idx, off in enumerate(is_off):
        if off == 1:
            if run_start is None:
                run_start = idx
        elif run_start is not None:
            if idx - run_start >= 3:
                start = max(0, run_start - 1)
                end = min(len(window), idx + 1)
                window[start:end] = 1
            run_start = None
    if run_start is not None and len(is_off) - run_start >= 3:
        start = max(0, run_start - 1)
        window[start:] = 1

    features["is_long_weekend_window"] = window


def _add_event_cycle_features(features: pd.DataFrame) -> None:
    """Add IRIAM event cycle features based on the fixed Tuesday-Monday schedule.

    IRIAM events always start on Tuesday and end on Monday (7-day cycle).
    weekday_num: 0=Monday, 1=Tuesday, ..., 6=Sunday

    event_day: 1 (Tuesday/start) through 7 (Monday/end)
    event_progress: 0.0 (start) to 1.0 (end)
    is_event_start: 1 on Tuesday (event day 1)
    is_event_end: 1 on Monday (event day 7, deadline rush)
    is_weekend_in_event: 1 on Saturday/Sunday within the event cycle
    """
    weekday_num = features["weekday_num"].to_numpy(dtype=int)

    # Tuesday=1, Wednesday=2, ..., Sunday=6, Monday=7
    event_day = ((weekday_num - 1) % 7) + 1

    features["event_day"] = event_day
    features["event_progress"] = (event_day - 1) / 6.0
    features["is_event_start"] = (event_day == 1).astype(int)
    features["is_event_end"] = (event_day == 7).astype(int)
    features["is_weekend_in_event"] = ((event_day == 5) | (event_day == 6)).astype(int)


def _add_gap_decay_features(features: pd.DataFrame, target_series: pd.Series) -> None:
    """Add features that capture irregular observation gaps and time decay.

    days_since_last_obs: number of calendar days since the last non-NaN observation
    decay_weight: exponential decay factor (half-life=7 days) measuring recency
    """
    dates = pd.to_datetime(features["date"])
    has_value = target_series.notna()

    days_since = np.full(len(features), np.nan)
    last_obs_date = None
    for i in range(len(features)):
        if has_value.iloc[i]:
            last_obs_date = dates.iloc[i]
            days_since[i] = 0.0
        elif last_obs_date is not None:
            days_since[i] = (dates.iloc[i] - last_obs_date).days

    features["days_since_last_obs"] = days_since
    half_life = 7.0
    features["decay_weight"] = np.where(
        np.isnan(days_since), 0.0, np.exp(-np.log(2) * np.nan_to_num(days_since) / half_life)
    )


def _add_large_holiday_clusters(features: pd.DataFrame) -> None:
    """Flag major Japanese holiday periods (GW, Obon, New Year)."""
    dates = pd.to_datetime(features["date"])
    if dates.empty:
        features["is_golden_week"] = 0
        features["is_obon"] = 0
        features["is_new_year"] = 0
        return

    # Golden Week (April 29 - May 6)
    is_gw = ((dates.dt.month == 4) & (dates.dt.day >= 29)) | ((dates.dt.month == 5) & (dates.dt.day <= 6))
    
    # Obon (August 13 - August 16)
    is_obon = (dates.dt.month == 8) & (dates.dt.day >= 13) & (dates.dt.day <= 16)
    
    # New Year (December 29 - January 3)
    is_new_year = ((dates.dt.month == 12) & (dates.dt.day >= 29)) | ((dates.dt.month == 1) & (dates.dt.day <= 3))

    features["is_golden_week"] = is_gw.astype(int)
    features["is_obon"] = is_obon.astype(int)
    features["is_new_year"] = is_new_year.astype(int)


def _add_platform_activity_features(features: pd.DataFrame, df: pd.DataFrame, current_target: str) -> None:
    """Calculate platform-wide base-tier averages as lagged context indicators."""
    base_targets = ["S1 +2", "A1 +2", "B1 +2"]
    cols = [c for c in base_targets if c in df.columns and c != current_target]
    if not cols:
        # Fallback columns if none found
        features["platform_avg_lag_1"] = 0.0
        features["platform_avg_lag_7"] = 0.0
        features["platform_trend_7"] = 0.0
        return

    # Average of the selected base borders (imputing NaNs dynamically)
    df_filled = df[cols].ffill().bfill().fillna(0.0)
    platform_avg = df_filled.mean(axis=1)

    # Shift values to prevent data leakage (use lagged metrics)
    features["platform_avg_lag_1"] = platform_avg.shift(1).fillna(0.0)
    features["platform_avg_lag_7"] = platform_avg.shift(7).fillna(0.0)
    
    # 7-day rolling mean of the 1-day lag to capture the general trend
    features["platform_trend_7"] = features["platform_avg_lag_1"].rolling(7, min_periods=1).mean().fillna(0.0)



