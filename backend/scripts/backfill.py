from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.bhavcopy_fetcher import EQUITY_SYMBOLS, refresh_segment_latest, upsert_ohlc_from_df, fetch_ohlc_yfinance
from app.db import SessionLocal
from app.pivot import compute_pivots_for_date


def backfill_equity(
    db: Session,
    start: date,
    end: date,
) -> None:
    df = fetch_ohlc_yfinance(EQUITY_SYMBOLS, start=start, end=end)
    upsert_ohlc_from_df(db, df, segment="equity")

    for d in sorted({d for d in df["date"].unique()}):
        compute_pivots_for_date(db, target_date=d, segment="equity")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        today = date.today()
        start = today - timedelta(days=365)
        backfill_equity(db, start=start, end=today)
    finally:
        db.close()

