from __future__ import annotations

from datetime import date
from typing import Dict, List

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .db import OHLC, Pivot


def _previous_trading_date(db: Session, current: date, segment: str) -> date | None:
    stmt = (
        select(OHLC.date)
        .where(and_(OHLC.segment == segment, OHLC.date < current))
        .order_by(OHLC.date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def compute_pivots_for_date(db: Session, target_date: date, segment: str) -> None:
    prev_date = _previous_trading_date(db, target_date, segment)
    if prev_date is None:
        return

    prev_bars = (
        db.query(OHLC)
        .filter(OHLC.segment == segment, OHLC.date == prev_date)
        .all()
    )
    if not prev_bars:
        return

    for bar in prev_bars:
        h = bar.high
        l = bar.low
        c = bar.close
        p = (h + l + c) / 3.0
        r1 = (p * 2) - l
        r2 = p + (h - l)
        s1 = (p * 2) - h
        s2 = p - (h - l)

        existing = (
            db.query(Pivot)
            .filter(
                Pivot.symbol == bar.symbol,
                Pivot.date == target_date,
                Pivot.segment == segment,
            )
            .one_or_none()
        )
        if existing:
            existing.pivot = p
            existing.r1 = r1
            existing.r2 = r2
            existing.s1 = s1
            existing.s2 = s2
        else:
            db.add(
                Pivot(
                    symbol=bar.symbol,
                    segment=segment,
                    date=target_date,
                    pivot=p,
                    r1=r1,
                    r2=r2,
                    s1=s1,
                    s2=s2,
                )
            )

    db.commit()


def find_r1_breakouts_for_date(
    db: Session,
    date: date,
    segment: str,
) -> List[Dict]:
    ohlc_rows = (
        db.query(OHLC)
        .filter(OHLC.date == date, OHLC.segment == segment)
        .all()
    )
    pivot_rows = (
        db.query(Pivot)
        .filter(Pivot.date == date, Pivot.segment == segment)
        .all()
    )
    pivot_by_symbol = {p.symbol: p for p in pivot_rows}

    results: List[Dict] = []
    for o in ohlc_rows:
        p = pivot_by_symbol.get(o.symbol)
        if not p:
            continue
        if o.high >= p.r1 and o.close > p.r1:
            results.append(
                {
                    "symbol": o.symbol,
                    "segment": o.segment,
                    "date": o.date,
                    "open": o.open,
                    "high": o.high,
                    "low": o.low,
                    "close": o.close,
                    "pivot": p.pivot,
                    "r1": p.r1,
                }
            )

    return results

