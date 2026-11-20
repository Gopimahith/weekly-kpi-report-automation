"""Generate SYNTHETIC e-commerce orders for demonstrating the report.

The data is random and for demonstration only. It includes a few duplicate
order ids and one unusually high-revenue day so the cleaning and anomaly
logic have something to find.

Usage: python src/generate_sample_orders.py --days 28 --out data/sample_orders.csv
"""
import argparse
import os
import random

import pandas as pd

CATEGORIES = {"Apparel": 0.22, "Footwear": 0.18, "Electronics": 0.08, "Home": 0.10, "Beauty": 0.06}


def generate(days: int = 28, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    start = pd.Timestamp("2026-10-01")
    rows, n = [], 1
    spike_day = days - 3
    for d in range(days):
        count = rng.randint(40, 60) + (120 if d == spike_day else 0)
        for _ in range(count):
            cat = rng.choice(list(CATEGORIES))
            rows.append(
                {
                    "order_id": f"O{n:06d}",
                    "order_date": (start + pd.Timedelta(days=d)).strftime("%Y-%m-%d"),
                    "category": cat,
                    "order_value": round(rng.uniform(15, 220), 2),
                    "returned": int(rng.random() < CATEGORIES[cat]),
                }
            )
            n += 1
    df = pd.DataFrame(rows)
    dupes = df.sample(5, random_state=seed)
    return pd.concat([df, dupes], ignore_index=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--out", default="data/sample_orders.csv")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    generate(args.days).to_csv(args.out, index=False)
    print(f"Wrote synthetic orders to {args.out}")
