import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


MONTH_PATTERN = re.compile(r"(?P<year>\d{4})年\s*\n?\s*(?P<month>\d{1,2})月")


@dataclass
class NormalizeResult:
    output_path: Path
    rows_total: int
    rows_data: int
    month_headers: int
    dropped_rows: int


def _load_raw(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return pd.read_excel(path, sheet_name=0, header=None)
    if ext == ".csv":
        return pd.read_csv(path, header=None)
    raise ValueError(f"Unsupported extension: {ext}")


def normalize_raw_dataset(input_path: Path, output_path: Path) -> NormalizeResult:
    df = _load_raw(input_path)
    if df.empty:
        raise ValueError("Input dataset is empty.")

    header = [str(v).strip() for v in df.iloc[0].tolist()]
    feature_names = header[2:]
    records: list[dict[str, object]] = []

    current_year: int | None = None
    current_month: int | None = None
    month_headers = 0
    dropped_rows = 0

    for _, row in df.iterrows():
        col0 = "" if pd.isna(row.iloc[0]) else str(row.iloc[0]).strip()
        col1 = "" if pd.isna(row.iloc[1]) else str(row.iloc[1]).strip()

        month_match = MONTH_PATTERN.search(col0)
        if month_match:
            current_year = int(month_match.group("year"))
            current_month = int(month_match.group("month"))
            month_headers += 1
            continue

        if col1 == "曜日" or not col0:
            dropped_rows += 1
            continue

        day_val = pd.to_numeric(row.iloc[0], errors="coerce")
        if pd.isna(day_val):
            dropped_rows += 1
            continue

        day_from_serial = pd.to_datetime(int(day_val), unit="D", origin="1899-12-30").day
        if current_year is None or current_month is None:
            dropped_rows += 1
            continue

        try:
            date = pd.Timestamp(year=current_year, month=current_month, day=day_from_serial)
        except ValueError:
            dropped_rows += 1
            continue

        record: dict[str, object] = {
            "date": date.strftime("%Y-%m-%d"),
            "year": int(date.year),
            "month": int(date.month),
            "day": int(date.day),
            "weekday_text": col1,
            "weekday_num": int(date.weekday()),
            "quarter": int((date.month - 1) // 3 + 1),
            "is_month_start": int(date.day == 1),
            "is_month_end": int(date.is_month_end),
            "season": _season_from_month(date.month),
        }

        for i, value in enumerate(row.iloc[2:].tolist()):
            name = feature_names[i]
            if pd.isna(value):
                record[name] = None
                continue
            s = str(value).strip()
            if s == "未登録" or s == "":
                record[name] = None
                continue
            num = pd.to_numeric(s, errors="coerce")
            record[name] = float(num) if pd.notna(num) else None

        records.append(record)

    normalized = pd.DataFrame(records).sort_values("date")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False, encoding="utf-8")

    return NormalizeResult(
        output_path=output_path,
        rows_total=len(df),
        rows_data=len(normalized),
        month_headers=month_headers,
        dropped_rows=dropped_rows,
    )


def _season_from_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"

