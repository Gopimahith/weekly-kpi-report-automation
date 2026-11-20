"""Turn a raw orders CSV into a weekly KPI report (Excel + Markdown).

Replaces the manual weekly routine of filtering orders, building pivot tables
and typing a summary. Metric definitions live in docs/metric_definitions.md.

Usage:
    python src/kpi_report.py --input data/sample_orders.csv --outdir output
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

REQUIRED = ["order_id", "order_date", "category", "order_value", "returned"]
ANOMALY_Z = 2.0  # a day is flagged when |z-score of daily revenue| >= 2


def load_orders(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df = df.drop_duplicates(subset="order_id").copy()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["order_value"] = pd.to_numeric(df["order_value"], errors="coerce")
    df["returned"] = df["returned"].astype(str).str.lower().isin({"1", "true", "yes", "y"})
    df = df.dropna(subset=["order_date", "order_value"])
    return df[df["order_value"] >= 0]


def summarize(df: pd.DataFrame) -> dict:
    """Headline KPIs for a set of orders."""
    n = len(df)
    kept = df[~df["returned"]]
    return {
        "orders": n,
        "gross_revenue": round(float(df["order_value"].sum()), 2),
        "net_revenue": round(float(kept["order_value"].sum()), 2),
        "avg_order_value": round(float(df["order_value"].mean()), 2) if n else 0.0,
        "return_rate": round(float(df["returned"].mean()), 4) if n else 0.0,
    }


def split_weeks(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (current_week, previous_week) = the latest 7 days and the 7 before."""
    end = df["order_date"].max().normalize()
    cur = df[df["order_date"] > end - pd.Timedelta(days=7)]
    prev = df[(df["order_date"] <= end - pd.Timedelta(days=7)) & (df["order_date"] > end - pd.Timedelta(days=14))]
    return cur, prev


def pct_change(new: float, old: float) -> float | None:
    return None if old == 0 else round((new - old) / old, 4)


def daily_with_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        df.assign(day=df["order_date"].dt.date)
        .groupby("day")
        .agg(orders=("order_id", "count"), revenue=("order_value", "sum"))
        .reset_index()
    )
    std = daily["revenue"].std(ddof=0)
    daily["z_score"] = 0.0 if std == 0 else ((daily["revenue"] - daily["revenue"].mean()) / std).round(2)
    daily["anomaly"] = daily["z_score"].abs() >= ANOMALY_Z
    daily["revenue"] = daily["revenue"].round(2)
    return daily


def category_table(df: pd.DataFrame) -> pd.DataFrame:
    t = (
        df.groupby("category")
        .agg(orders=("order_id", "count"), revenue=("order_value", "sum"), return_rate=("returned", "mean"))
        .reset_index()
        .sort_values("revenue", ascending=False)
    )
    t["revenue"] = t["revenue"].round(2)
    t["return_rate"] = t["return_rate"].round(4)
    return t


def build_markdown(cur: dict, prev: dict, cats: pd.DataFrame, anomalies: pd.DataFrame) -> str:
    def line(label, key, fmt):
        ch = pct_change(cur[key], prev[key])
        ch_txt = "n/a" if ch is None else f"{ch:+.1%}"
        return f"| {label} | {fmt(cur[key])} | {fmt(prev[key])} | {ch_txt} |"

    money = lambda v: f"{v:,.2f}"
    pct = lambda v: f"{v:.1%}"
    lines = [
        "# Weekly KPI report",
        "",
        "| KPI | This week | Last week | Change |",
        "|---|---|---|---|",
        line("Orders", "orders", lambda v: f"{v:,}"),
        line("Gross revenue", "gross_revenue", money),
        line("Net revenue (excl. returns)", "net_revenue", money),
        line("Average order value", "avg_order_value", money),
        line("Return rate", "return_rate", pct),
        "",
    ]
    worst = cats.sort_values("return_rate", ascending=False).iloc[0]
    lines.append(f"**Highest return rate (this week):** {worst['category']} at {worst['return_rate']:.1%}.")
    lines.append("")
    if anomalies.empty:
        lines.append("**Anomalies:** none. No day's revenue was 2 or more standard deviations from the period average.")
    else:
        lines.append("**Anomalies (daily revenue 2+ standard deviations from average):**")
        for _, r in anomalies.iterrows():
            lines.append(f"- {r['day']}: revenue {r['revenue']:,.2f} (z = {r['z_score']})")
    return "\n".join(lines) + "\n"


def write_excel(path: str, cur: dict, prev: dict, daily: pd.DataFrame, cats: pd.DataFrame) -> None:
    summary = pd.DataFrame(
        {
            "KPI": ["Orders", "Gross revenue", "Net revenue", "Average order value", "Return rate"],
            "This week": [cur["orders"], cur["gross_revenue"], cur["net_revenue"], cur["avg_order_value"], cur["return_rate"]],
            "Last week": [prev["orders"], prev["gross_revenue"], prev["net_revenue"], prev["avg_order_value"], prev["return_rate"]],
        }
    )
    summary["Change"] = [
        pct_change(a, b) for a, b in zip(summary["This week"], summary["Last week"])
    ]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        daily.to_excel(xw, sheet_name="Daily", index=False)
        cats.to_excel(xw, sheet_name="Categories", index=False)
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DDEBF7")
            for i, col in enumerate(ws.columns, start=1):
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2
                ws.column_dimensions[get_column_letter(i)].width = min(width, 40)
        s = xw.book["Summary"]
        for row in range(2, s.max_row + 1):
            if s.cell(row, 1).value == "Return rate":
                for col in (2, 3):
                    s.cell(row, col).number_format = "0.0%"
            s.cell(row, 4).number_format = "+0.0%;-0.0%"


def run(input_path: str, outdir: str) -> dict:
    os.makedirs(outdir, exist_ok=True)
    df = load_orders(input_path)
    cur_df, prev_df = split_weeks(df)
    cur, prev = summarize(cur_df), summarize(prev_df)
    daily = daily_with_anomalies(df)
    cats = category_table(cur_df)
    anomalies = daily[daily["anomaly"]]
    md = build_markdown(cur, prev, cats, anomalies)
    with open(os.path.join(outdir, "weekly_report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    write_excel(os.path.join(outdir, "weekly_report.xlsx"), cur, prev, daily, cats)
    return {"current": cur, "previous": prev, "anomaly_days": int(len(anomalies))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()
    print(run(args.input, args.outdir))
