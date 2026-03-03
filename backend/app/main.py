from datetime import date
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import get_settings
from .condition_engine import evaluate_conditions_for_rows
from .db import OHLC, get_db, get_future_contracts, init_db
from .pivot import compute_pivots_from_ohlc, find_r1_breakouts_for_date
from .bhavcopy_fetcher import (
    backfill_futures_for_options,
    get_near_next_far_expiries,
    refresh_latest_for_all_segments,
)


settings = get_settings()

app = FastAPI(title="NSE Equity Stock Scanner API")

# Allow frontend from any origin (Hostinger, localhost, file). Set CORS_ORIGINS in env to restrict.
origins = [str(o) for o in settings.cors_origins] if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    expiry_date: Optional[date] = None


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
    expiry_date: Optional[date] = None


class ContractRow(BaseModel):
    symbol: str
    expiry_date: date


class OHLCRow(BaseModel):
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    segment: str = "equity"
    expiry_date: Optional[date] = None


class ScanRequest(BaseModel):
    date: date
    segment: str = "equity"
    expiry_date: Optional[date] = None  # for segment=future: contract expiry
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
    expiry_date: Optional[date] = None


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/pivots", response_model=List[PivotRow])
def api_get_pivots(
    date: date = Query(...),
    segment: str = Query("equity"),
    expiry_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Pivots computed at runtime from previous day OHLC (not stored in DB). For futures, pass expiry_date."""
    rows = compute_pivots_from_ohlc(db, date, segment, expiry_date)
    return [
        PivotRow(
            symbol=r["symbol"],
            segment=r["segment"],
            date=r["date"],
            pivot=r["pivot"],
            r1=r["r1"],
            r2=r["r2"],
            s1=r["s1"],
            s2=r["s2"],
            expiry_date=r.get("expiry_date"),
        )
        for r in sorted(rows, key=lambda x: (x["symbol"], x.get("expiry_date") or date.min))
    ]


@app.get("/api/ohlc", response_model=List[OHLCRow])
def api_get_ohlc(
    date: date = Query(..., description="Trading date"),
    segment: str = Query("equity"),
    expiry_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Return all OHLC records for the given date (and segment; for future, optional expiry_date)."""
    q = db.query(OHLC).filter(OHLC.date == date, OHLC.segment == segment)
    if segment == "future" and expiry_date is not None:
        q = q.filter(OHLC.expiry_date == expiry_date)
    rows = q.order_by(OHLC.symbol).all()
    return [
        OHLCRow(
            symbol=r.symbol,
            date=r.date,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=getattr(r, "volume", None),
            segment=r.segment,
            expiry_date=getattr(r, "expiry_date", None),
        )
        for r in rows
    ]


@app.get("/api/contracts", response_model=List[ContractRow])
def api_get_contracts(segment: str = Query("future"), db: Session = Depends(get_db)):
    """List of future contracts (symbol, expiry_date) for the contract selector. Only segment=future has contracts."""
    if segment != "future":
        return []
    return [ContractRow(symbol=c["symbol"], expiry_date=c["expiry_date"]) for c in get_future_contracts(db)]


@app.get("/api/r1-breakouts", response_model=List[BreakoutRow])
def api_get_r1_breakouts(
    date: date = Query(...),
    segment: str = Query("equity"),
    expiry_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    breakouts = find_r1_breakouts_for_date(db, date=date, segment=segment, expiry_date=expiry_date)
    return [
        BreakoutRow(
            symbol=b["symbol"],
            segment=b["segment"],
            date=b["date"],
            open=b["open"],
            high=b["high"],
            low=b["low"],
            close=b["close"],
            pivot=b["pivot"],
            r1=b["r1"],
            expiry_date=b.get("expiry_date"),
        )
        for b in breakouts
    ]


@app.post("/api/scan", response_model=List[ScanRow])
def api_scan(req: ScanRequest, db: Session = Depends(get_db)):
    """Scan: OHLC from DB, pivots computed at runtime. For futures, filter by req.expiry_date."""
    q = db.query(OHLC).filter(OHLC.date == req.date, OHLC.segment == req.segment)
    if req.segment == "future" and req.expiry_date is not None:
        q = q.filter(OHLC.expiry_date == req.expiry_date)
    ohlc_rows = q.all()

    pivot_rows = compute_pivots_from_ohlc(db, req.date, req.segment, req.expiry_date)
    key = lambda r: (r["symbol"], r.get("expiry_date"))
    pivot_by_key = {key(r): r for r in pivot_rows}

    dataset = []
    for o in ohlc_rows:
        k = (o.symbol, getattr(o, "expiry_date", None))
        p = pivot_by_key.get(k)
        row = {
            "symbol": o.symbol,
            "segment": o.segment,
            "date": o.date,
            "open": o.open,
            "high": o.high,
            "low": o.low,
            "close": o.close,
            "volume": o.volume,
            "pivot": p["pivot"] if p else None,
            "r1": p["r1"] if p else None,
            "r2": p["r2"] if p else None,
            "s1": p["s1"] if p else None,
            "s2": p["s2"] if p else None,
            "expiry_date": getattr(o, "expiry_date", None),
        }
        dataset.append(row)

    filtered_rows = evaluate_conditions_for_rows(dataset, req.conditions, req.combine)
    return [ScanRow(**r) for r in filtered_rows]


@app.get("/api/futures/expiries")
def api_futures_expiries(
    mode: str = Query(..., description="latest or historical"),
    ref_date: Optional[date] = Query(None, alias="date", description="Required when mode=historical (YYYY-MM-DD)"),
) -> Any:
    """Returns near, next, far contract info for Latest (today) or Historical (given date)."""
    if mode not in ("latest", "historical"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be 'latest' or 'historical'")
    if mode == "historical" and ref_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date is required when mode=historical")
    reference = ref_date if mode == "historical" and ref_date else date.today()
    return get_near_next_far_expiries(reference)


class BackfillFuturesRequest(BaseModel):
    mode: str  # "latest" | "historical"
    date: Optional[date] = None  # required when mode=historical
    contract: str  # "near" | "next" | "far" | "all"


@app.post("/api/backfill/futures")
def api_backfill_futures(
    req: BackfillFuturesRequest,
    x_refresh_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Backfill NIFTY futures for one date. Latest = today; Historical = req.date. contract: near|next|far|all."""
    if x_refresh_secret != settings.refresh_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if req.mode not in ("latest", "historical"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be 'latest' or 'historical'")
    if req.mode == "historical" and req.date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date is required when mode=historical")
    if req.contract not in ("near", "next", "far", "all"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="contract must be near, next, far, or all")
    for_date = req.date if req.mode == "historical" else date.today()
    try:
        n = backfill_futures_for_options(db, for_date, req.contract)
        return {"status": "ok", "rows_upserted": n}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


@app.post("/api/refresh")
def api_refresh(
    x_refresh_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Daily refresh: fetch latest OHLC (equity + futures). Pivots are computed at runtime only, not stored."""
    if x_refresh_secret != settings.refresh_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        refresh_latest_for_all_segments(db)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

