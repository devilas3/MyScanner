"""
Pivot calculations at runtime only (no DB storage).
Uses previous day's OHLC from DB to compute P, R1, R2, S1, S2 for the given date.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .db import OHLC


def _previous_trading_date(
    db: Session,
    current: date,
    segment: str,
    expiry_date: Optional[date] = None,
) -> Optional[date]:
    q = (
        select(OHLC.date)
        .where(and_(OHLC.segment == segment, OHLC.date < current))
    )
    if segment == "future" and expiry_date is not None:
        q = q.where(OHLC.expiry_date == expiry_date)
    q = q.order_by(OHLC.date.desc()).limit(1)
    return db.execute(q).scalar_one_or_none()


def _pivot_from_bar(high: float, low: float, close: float) -> Dict[str, float]:
    p = (high + low + close) / 3.0
    return {
        "pivot": p,
        "r1": (p * 2) - low,
        "r2": p + (high - low),
        "s1": (p * 2) - high,
        "s2": p - (high - low),
    }


def compute_pivots_from_ohlc(
    db: Session,
    target_date: date,
    segment: str,
    expiry_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Compute pivot levels at runtime from OHLC. No DB write.
    For equity: segment='equity', expiry_date=None.
    For future: segment='future', expiry_date=contract expiry (e.g. last Thu of month).
    """
    prev_date = _previous_trading_date(db, target_date, segment, expiry_date)
    if prev_date is None:
        return []

    q = db.query(OHLC).filter(
        OHLC.segment == segment,
        OHLC.date == prev_date,
    )
    if segment == "future" and expiry_date is not None:
        q = q.filter(OHLC.expiry_date == expiry_date)
    prev_bars = q.all()

    out: List[Dict[str, Any]] = []
    for bar in prev_bars:
        vals = _pivot_from_bar(bar.high, bar.low, bar.close)
        row = {
            "symbol": bar.symbol,
            "segment": segment,
            "date": target_date,
            "expiry_date": getattr(bar, "expiry_date", None),
            **vals,
        }
        out.append(row)
    return out


def find_r1_breakouts_for_date(
    db: Session,
    target_date: date,
    segment: str,
    expiry_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """R1 breakouts at runtime: high >= r1 and close > r1, using pivots computed from OHLC."""
    ohlc_rows = (
        db.query(OHLC)
        .filter(OHLC.date == target_date, OHLC.segment == segment)
    )
    if segment == "future" and expiry_date is not None:
        ohlc_rows = ohlc_rows.filter(OHLC.expiry_date == expiry_date)
    ohlc_rows = ohlc_rows.all()

    pivot_rows = compute_pivots_from_ohlc(db, target_date, segment, expiry_date)
    key = lambda r: (r["symbol"], r.get("expiry_date"))
    pivot_by_key = {key(r): r for r in pivot_rows}

    results: List[Dict[str, Any]] = []
    for o in ohlc_rows:
        k = (o.symbol, getattr(o, "expiry_date", None))
        p = pivot_by_key.get(k)
        if not p:
            continue
        if o.high >= p["r1"] and o.close > p["r1"]:
            results.append({
                "symbol": o.symbol,
                "segment": o.segment,
                "date": o.date,
                "open": o.open,
                "high": o.high,
                "low": o.low,
                "close": o.close,
                "pivot": p["pivot"],
                "r1": p["r1"],
                "expiry_date": getattr(o, "expiry_date", None),
            })
    return results
