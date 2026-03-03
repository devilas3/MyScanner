from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from .db import OHLC, get_latest_ohlc_date
from .pivot import compute_pivots_for_date


# Initial simple universe – adjust to your needs
EQUITY_SYMBOLS: List[str] = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "AXISBANK.NS",
    "LT.NS",
    "ITC.NS",
]


def _strip_suffix(symbol: str) -> str:
    return symbol.replace(".NS", "")


def fetch_ohlc_yfinance(
    symbols: Iterable[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    if start > end:
        return pd.DataFrame()

    tickers = list(symbols)
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end + timedelta(days=1),
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    rows = []
    if isinstance(data.columns, pd.MultiIndex):
        for sym in tickers:
            if sym not in data.columns.levels[0]:
                continue
            df_sym = data[sym].dropna()
            for idx, r in df_sym.iterrows():
                rows.append(
                    {
                        "symbol": _strip_suffix(sym),
                        "date": idx.date(),
                        "open": float(r["Open"]),
                        "high": float(r["High"]),
                        "low": float(r["Low"]),
                        "close": float(r["Close"]),
                        "volume": float(r.get("Volume", 0.0)),
                    }
                )
    else:
        df = data.dropna()
        for idx, r in df.iterrows():
            rows.append(
                {
                    "symbol": _strip_suffix(tickers[0]),
                    "date": idx.date(),
                    "open": float(r["Open"]),
                    "high": float(r["High"]),
                    "low": float(r["Low"]),
                    "close": float(r["Close"]),
                    "volume": float(r.get("Volume", 0.0)),
                }
            )

    return pd.DataFrame(rows)


def upsert_ohlc_from_df(db: Session, df: pd.DataFrame, segment: str) -> None:
    if df.empty:
        return

    for _, row in df.iterrows():
        existing = (
            db.query(OHLC)
            .filter(
                OHLC.symbol == row["symbol"],
                OHLC.date == row["date"],
                OHLC.segment == segment,
            )
            .one_or_none()
        )
        if existing:
            existing.open = row["open"]
            existing.high = row["high"]
            existing.low = row["low"]
            existing.close = row["close"]
            existing.volume = row["volume"]
        else:
            db.add(
                OHLC(
                    symbol=row["symbol"],
                    segment=segment,
                    date=row["date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            )
    db.commit()


def refresh_segment_latest(db: Session, segment: str, symbols: Iterable[str]) -> None:
    latest = get_latest_ohlc_date(db, segment)
    today = date.today()
    if latest is None:
        start = today - timedelta(days=60)
    else:
        start = latest + timedelta(days=1)

    df = fetch_ohlc_yfinance(symbols, start=start, end=today)
    if df.empty:
        return

    upsert_ohlc_from_df(db, df, segment=segment)

    for d in sorted({d for d in df["date"].unique()}):
        compute_pivots_for_date(db, target_date=d, segment=segment)


def refresh_latest_for_all_segments(db: Session) -> None:
    refresh_segment_latest(db, segment="equity", symbols=EQUITY_SYMBOLS)
    # Placeholder: extend with real futures data source later

