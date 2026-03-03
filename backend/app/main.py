from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import get_settings
from .condition_engine import evaluate_conditions_for_rows
from .db import OHLC, Pivot, get_db, init_db
from .pivot import compute_pivots_for_date, find_r1_breakouts_for_date
from .bhavcopy_fetcher import refresh_latest_for_all_segments


settings = get_settings()

app = FastAPI(title="NSE Equity Stock Scanner API")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class PivotRow(BaseModel):
    symbol: str
    segment: str
    date: date
    pivot: float
    r1: float
    r2: float
    s1: float
    s2: float


class BreakoutRow(BaseModel):
    symbol: str
    segment: str
    date: date
    open: float
    high: float
    low: float
    close: float
    pivot: float
    r1: float


class ScanRequest(BaseModel):
    date: date
    segment: str = "equity"
    conditions: List[str]
    combine: str = "and"


class ScanRow(BaseModel):
    symbol: str
    segment: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    pivot: Optional[float] = None
    r1: Optional[float] = None
    r2: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/pivots", response_model=List[PivotRow])
def api_get_pivots(date: date = Query(...), segment: str = Query("equity"), db: Session = Depends(get_db)):
    rows = (
        db.query(Pivot)
        .filter(Pivot.date == date, Pivot.segment == segment)
        .order_by(Pivot.symbol.asc())
        .all()
    )
    return [
        PivotRow(
            symbol=r.symbol,
            segment=r.segment,
            date=r.date,
            pivot=r.pivot,
            r1=r.r1,
            r2=r.r2,
            s1=r.s1,
            s2=r.s2,
        )
        for r in rows
    ]


@app.get("/api/r1-breakouts", response_model=List[BreakoutRow])
def api_get_r1_breakouts(
    date: date = Query(...), segment: str = Query("equity"), db: Session = Depends(get_db)
):
    return find_r1_breakouts_for_date(db, date=date, segment=segment)


@app.post("/api/scan", response_model=List[ScanRow])
def api_scan(req: ScanRequest, db: Session = Depends(get_db)):
    # Load OHLC + pivots for the requested date and segment
    ohlc_rows = (
        db.query(OHLC)
        .filter(OHLC.date == req.date, OHLC.segment == req.segment)
        .all()
    )
    pivot_rows = (
        db.query(Pivot)
        .filter(Pivot.date == req.date, Pivot.segment == req.segment)
        .all()
    )
    pivot_by_symbol = {p.symbol: p for p in pivot_rows}

    dataset = []
    for o in ohlc_rows:
        p = pivot_by_symbol.get(o.symbol)
        row = {
            "symbol": o.symbol,
            "segment": o.segment,
            "date": o.date,
            "open": o.open,
            "high": o.high,
            "low": o.low,
            "close": o.close,
            "volume": o.volume,
            "pivot": getattr(p, "pivot", None) if p else None,
            "r1": getattr(p, "r1", None) if p else None,
            "r2": getattr(p, "r2", None) if p else None,
            "s1": getattr(p, "s1", None) if p else None,
            "s2": getattr(p, "s2", None) if p else None,
        }
        dataset.append(row)

    filtered_rows = evaluate_conditions_for_rows(dataset, req.conditions, req.combine)

    return [ScanRow(**r) for r in filtered_rows]


@app.post("/api/refresh", status_code=status.HTTP_204_NO_CONTENT)
def api_refresh(
    x_refresh_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if x_refresh_secret != settings.refresh_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    refresh_latest_for_all_segments(db)
    return None

