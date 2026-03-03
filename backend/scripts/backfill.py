from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# So "python scripts/backfill.py" from backend/ finds the app package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.bhavcopy_fetcher import (
    EQUITY_SYMBOLS,
    fetch_ohlc_yfinance,
    upsert_ohlc_from_df,
)
from app.db import SessionLocal
from app.pivot import compute_pivots_for_date


def backfill_equity(
    db: Session,
    start: date,
    end: date,
) -> None:
    print(f"Fetching OHLC for {len(EQUITY_SYMBOLS)} symbols from {start} to {end}...")
    df = fetch_ohlc_yfinance(EQUITY_SYMBOLS, start=start, end=end)
    if df.empty:
        print("No data returned from yfinance. Check symbols and date range.")
        return
    print(f"Got {len(df)} rows. Upserting into DB...")
    upsert_ohlc_from_df(db, df, segment="equity")
    dates = sorted({d for d in df["date"].unique()})
    print(f"Computing pivots for {len(dates)} dates...")
    for d in dates:
        compute_pivots_for_date(db, target_date=d, segment="equity")
    print("Backfill done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill equity OHLC and pivots into the database.")
    parser.add_argument(
        "--years",
        type=float,
        default=2,
        help="Number of years of history to fetch (default: 2)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date YYYY-MM-DD (overrides --years)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()

    today = date.today()
    if args.end:
        end = date.fromisoformat(args.end)
    else:
        end = today
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = today - timedelta(days=int(args.years * 365))
    if start > end:
        start, end = end, start

    print(f"Backfill range: {start} to {end} ({args.years} years if default)")

    db = SessionLocal()
    try:
        backfill_equity(db, start=start, end=end)
    finally:
        db.close()

