from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Iterable, List, Optional

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .db import OHLC, get_latest_ohlc_date

BULK_UPSERT_CHUNK = 500

# NSE bhavcopy request headers (required by NSE)
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/csv",
    "Referer": "https://www.nseindia.com/",
}


def _last_thursday_of_month(d: date) -> date:
    """Last Thursday of the month for NSE F&O expiry."""
    last = calendar.monthrange(d.year, d.month)[1]
    last_day = date(d.year, d.month, last)
    # weekday: Monday=0, Thursday=3
    offset = (last_day.weekday() - 3) % 7
    if offset <= 0:
        return last_day - timedelta(days=-offset)
    return last_day - timedelta(days=7 - offset)


def _contract_label(expiry: date) -> str:
    """e.g. 2025-03-27 -> NIFTY25MAR"""
    return f"NIFTY{expiry.year % 100}{expiry.strftime('%b').upper()}"


def _next_three_expiries() -> List[date]:
    """Current month and next two months' last Thursday (NSE index futures expiry)."""
    today = date.today()
    expiries: List[date] = []
    for m in range(3):
        y = today.year
        month = today.month + m
        if month > 12:
            month -= 12
            y += 1
        expiries.append(_last_thursday_of_month(date(y, month, 1)))
    return sorted(set(expiries))


def fetch_nse_derivative_bhavcopy(for_date: date) -> Optional[pd.DataFrame]:
    """Fetch NSE derivatives bhavcopy CSV for a date. Returns DataFrame or None."""
    ddmonyy = for_date.strftime("%d%b%Y")  # 03MAR2025
    mon = for_date.strftime("%b").upper()
    year = for_date.year
    url = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{year}/{mon}/fo{ddmonyy}bhav.csv"
    try:
        r = requests.get(url, headers=NSE_HEADERS, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(pd.io.common.BytesIO(r.content))
        return df
    except Exception:
        return None


def fetch_futures_ohlc_for_date(for_date: date) -> pd.DataFrame:
    """
    Fetch NIFTY index futures OHLC for a date from NSE bhavcopy.
    Returns DataFrame with columns: symbol (contract e.g. NIFTY25MAR), date, open, high, low, close, volume, expiry_date.
    """
    df = fetch_nse_derivative_bhavcopy(for_date)
    if df is None or df.empty:
        return pd.DataFrame()

    # NSE fo*bhav.csv: INSTRUMENT, SYMBOL, EXPIRY_DT, OPEN, HIGH, LOW, CLOSE, CONTRACTS, etc.
    if "INSTRUMENT" in df.columns:
        df = df[df["INSTRUMENT"].astype(str).str.upper() == "FUTIDX"]
    if "SYMBOL" in df.columns:
        df = df[df["SYMBOL"].astype(str).str.upper() == "NIFTY"]
    if df.empty:
        return pd.DataFrame()

    # Expiry column
    exp_col = "EXPIRY_DT" if "EXPIRY_DT" in df.columns else ("EXPIRY DT" if "EXPIRY DT" in df.columns else None)
    if exp_col is None:
        return pd.DataFrame()
    try:
        df["_expiry"] = pd.to_datetime(df[exp_col], format="%d-%b-%Y", errors="coerce").dt.date
    except Exception:
        df["_expiry"] = pd.to_datetime(df[exp_col], errors="coerce").dt.date
    df = df.dropna(subset=["_expiry"])

    o = "OPEN" if "OPEN" in df.columns else "Open"
    h = "HIGH" if "HIGH" in df.columns else "High"
    l = "LOW" if "LOW" in df.columns else "Low"
    c = "CLOSE" if "CLOSE" in df.columns else "Close"
    vol = "CONTRACTS" if "CONTRACTS" in df.columns else "volume"

    out = []
    for exp, grp in df.groupby("_expiry"):
        exp_date = exp if hasattr(exp, "year") else exp
        row = grp.iloc[0]
        contract = _contract_label(exp_date)
        out.append({
            "symbol": contract,
            "date": for_date,
            "open": float(row[o]),
            "high": float(row[h]),
            "low": float(row[l]),
            "close": float(row[c]),
            "volume": float(grp[vol].sum()) if vol in grp.columns else 0.0,
            "expiry_date": exp_date,
        })
    return pd.DataFrame(out)


def upsert_ohlc_futures_from_df(db: Session, df: pd.DataFrame) -> None:
    """Bulk upsert futures OHLC. DataFrame must have symbol, date, open, high, low, close, volume, expiry_date."""
    if df.empty or "expiry_date" not in df.columns:
        return
    df = df.copy()
    df["segment"] = "future"
    cols = ["symbol", "date", "segment", "open", "high", "low", "close", "volume", "expiry_date"]
    rows = df[cols].to_dict("records")
    for i in range(0, len(rows), BULK_UPSERT_CHUNK):
        chunk = rows[i : i + BULK_UPSERT_CHUNK]
        stmt = pg_insert(OHLC).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date", "segment"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "expiry_date": stmt.excluded.expiry_date,
            },
        )
        db.execute(stmt)
        db.commit()


def refresh_futures_latest(db: Session) -> None:
    """Fetch latest NIFTY futures for next 3 expiry contracts and upsert."""
    today = date.today()
    for d in [today, today - timedelta(days=1)]:
        df = fetch_futures_ohlc_for_date(d)
        if not df.empty:
            upsert_ohlc_futures_from_df(db, df)


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

    df = df.copy()
    df["segment"] = segment
    rows = df[["symbol", "date", "segment", "open", "high", "low", "close", "volume"]].to_dict("records")

    for i in range(0, len(rows), BULK_UPSERT_CHUNK):
        chunk = rows[i : i + BULK_UPSERT_CHUNK]
        stmt = pg_insert(OHLC).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date", "segment"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        db.execute(stmt)
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


def refresh_latest_for_all_segments(db: Session) -> None:
    refresh_segment_latest(db, segment="equity", symbols=EQUITY_SYMBOLS)
    refresh_futures_latest(db)

