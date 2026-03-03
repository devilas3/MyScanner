from datetime import date
from typing import Generator
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _engine_url_with_ssl(url: str) -> str:
    """Ensure PostgreSQL URLs have sslmode=require for Supabase/cloud DBs."""
    if not url.startswith("postgresql"):
        return url
    parsed = urlparse(url)
    params = parse_qsl(parsed.query)
    if not any(k == "sslmode" for k, _ in params):
        params.append(("sslmode", "require"))
    new_query = urlencode(params)
    return urlunparse(parsed._replace(query=new_query))


_db_url = _engine_url_with_ssl(settings.database_url)
engine = create_engine(
    _db_url,
    future=True,
    poolclass=NullPool,  # works better when Render spins down (serverless)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class OHLC(Base):
    __tablename__ = "ohlc"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    segment = Column(String, index=True, nullable=False)  # "equity" | "future"
    date = Column(Date, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    expiry_date = Column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "date", "segment", name="uix_symbol_date_segment"),
    )


class Pivot(Base):
    __tablename__ = "pivots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    segment = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    pivot = Column(Float, nullable=False)
    r1 = Column(Float, nullable=False)
    r2 = Column(Float, nullable=False)
    s1 = Column(Float, nullable=False)
    s2 = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "date", "segment", name="uix_pivot_symbol_date_segment"),
    )


class RefreshLog(Base):
    __tablename__ = "refresh_log"

    id = Column(Integer, primary_key=True, index=True)
    segment = Column(String, unique=True, nullable=False)
    last_date = Column(Date, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_latest_ohlc_date(db: Session, segment: str) -> date | None:
    stmt = select(OHLC.date).where(OHLC.segment == segment).order_by(OHLC.date.desc()).limit(1)
    result = db.execute(stmt).scalar_one_or_none()
    return result

