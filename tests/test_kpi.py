import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import kpi_report as k  # noqa: E402
from generate_sample_orders import generate  # noqa: E402


def make(rows):
    return pd.DataFrame(rows, columns=["order_id", "order_date", "category", "order_value", "returned"])


def test_summarize_hand_calculated():
    df = make([
        ["1", "2026-10-01", "A", 100, False],
        ["2", "2026-10-01", "A", 50, True],
        ["3", "2026-10-02", "B", 50, False],
        ["4", "2026-10-02", "B", 100, False],
    ])
    df["order_date"] = pd.to_datetime(df["order_date"])
    s = k.summarize(df)
    assert s["orders"] == 4
    assert s["gross_revenue"] == 300
    assert s["net_revenue"] == 250      # excludes the returned 50
    assert s["avg_order_value"] == 75
    assert s["return_rate"] == 0.25


def test_pct_change_handles_zero_base():
    assert k.pct_change(110, 100) == 0.1
    assert k.pct_change(5, 0) is None


def test_load_orders_drops_duplicates_and_bad_rows(tmp_path):
    p = tmp_path / "o.csv"
    make([
        ["1", "2026-10-01", "A", 10, 0],
        ["1", "2026-10-01", "A", 10, 0],       # duplicate id
        ["2", "not-a-date", "A", 10, 0],       # bad date
        ["3", "2026-10-01", "A", -5, 0],       # negative value
        ["4", "2026-10-01", "A", "abc", 0],    # non-numeric value
        ["5", "2026-10-02", "A", 20, 1],
    ]).to_csv(p, index=False)
    df = k.load_orders(str(p))
    assert sorted(df["order_id"].astype(str)) == ["1", "5"]


def test_missing_column_raises(tmp_path):
    p = tmp_path / "o.csv"
    pd.DataFrame({"order_id": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        k.load_orders(str(p))


def test_anomaly_flags_the_spike_day():
    df = generate(28)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["returned"] = df["returned"].astype(bool)
    daily = k.daily_with_anomalies(df.drop_duplicates("order_id"))
    flagged = daily[daily["anomaly"]]
    assert len(flagged) >= 1
    assert flagged["revenue"].max() == daily["revenue"].max()


def test_end_to_end_writes_outputs(tmp_path):
    src = tmp_path / "orders.csv"
    generate(28).to_csv(src, index=False)
    out = tmp_path / "out"
    result = k.run(str(src), str(out))
    assert (out / "weekly_report.md").exists()
    assert (out / "weekly_report.xlsx").exists()
    assert result["current"]["orders"] > 0 and result["previous"]["orders"] > 0
    xl = pd.ExcelFile(out / "weekly_report.xlsx")
    assert set(xl.sheet_names) == {"Summary", "Daily", "Categories"}
    md = (out / "weekly_report.md").read_text()
    assert "Weekly KPI report" in md and "Return rate" in md
