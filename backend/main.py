"""
CivicSignal API: serves buying-signal data to the frontend.

Local:
    uvicorn main:app --reload --port 8000

Deployed (Render):
    uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db import get_db, init_db, Matter

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once before the app starts serving. Creates any missing tables so
    # a fresh database (a new Neon branch, or the SQLite file the tests use)
    # works without a manual migration step.
    init_db()
    yield
    # Nothing to tear down: SQLAlchemy's pool closes with the process.


app = FastAPI(title="CivicSignal API", version="0.2.0", lifespan=lifespan)

# Which browser origins may call this API.
#
# Comma-separated exact origins, for local dev and any custom domain:
#   ALLOWED_ORIGINS=http://localhost:3000,https://civicsignal.example.com
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# Vercel gives every single deployment its own immutable URL, and every
# preview branch another one, so an exact allowlist is unmaintainable: the
# hostname changes on every push. This pattern matches the project's own
# deployments and nothing else.
#
# Deliberately anchored at both ends. An unanchored pattern would also match
# something like https://evil.com/?x=civicsignal-.vercel.app, which is the
# classic way origin checks get bypassed.
ALLOWED_ORIGIN_REGEX = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"^https://civicsignal[a-z0-9-]*\.vercel\.app$",
)

# Still not "*". This API serves read-only public data today, but a wildcard
# is a habit that becomes a real problem the moment any endpoint stops being
# public, and it costs nothing to scope it now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def serialize(matter: Matter) -> dict:
    return {
        "id": matter.id,
        "source_client": matter.source_client,
        "matter_file": matter.matter_file,
        "matter_name": matter.matter_name,
        "matter_title": matter.matter_title,
        "matter_type": matter.matter_type,
        "matter_status": matter.matter_status,
        "matter_body": matter.matter_body,
        "intro_date": matter.intro_date,
        "agenda_date": matter.agenda_date,
        "signal_score": matter.signal_score,
        "signal_category": matter.signal_category,
        "signal_summary": matter.signal_summary,
    }


@app.get("/health")
def health():
    """
    Liveness check for the host platform and for keep-warm pings.

    Deliberately does NOT touch the database. A health check that queries
    Postgres reports the whole service as down whenever the database is
    merely asleep (Neon's free tier scales compute to zero after 5 minutes
    idle), which would cause the platform to restart a perfectly healthy
    process. Database reachability is a separate concern from "is this
    process alive and serving".
    """
    return {"status": "ok"}


@app.get("/api/clients")
def list_clients(db: Session = Depends(get_db)):
    """Distinct cities/counties present in the data, for the frontend filter."""
    rows = (
        db.query(Matter.source_client)
        .filter(Matter.source_client.isnot(None))
        .distinct()
        .order_by(Matter.source_client)
        .all()
    )
    return {"clients": [r[0] for r in rows]}


@app.get("/api/signals")
def list_signals(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Filter by title or matter file"),
    client: Optional[str] = Query(None, description="Filter by city/county (source_client)"),
    category: Optional[str] = Query(None, description="Filter by signal_category"),
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(100, le=200),
):
    query = db.query(Matter).filter(Matter.signal_score.isnot(None))

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Matter.matter_title.ilike(like)) | (Matter.matter_file.ilike(like))
        )
    if client:
        query = query.filter(Matter.source_client == client)
    if category:
        query = query.filter(Matter.signal_category == category)
    if min_score:
        query = query.filter(Matter.signal_score >= min_score)

    results = query.order_by(desc(Matter.signal_score)).limit(limit).all()
    return {"count": len(results), "results": [serialize(m) for m in results]}


@app.get("/api/signals/{matter_id}")
def get_signal(matter_id: int, db: Session = Depends(get_db)):
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        return {"error": "not found"}
    return serialize(matter)


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    scored = db.query(Matter).filter(Matter.signal_score.isnot(None))
    total = scored.count()
    high_signal = scored.filter(Matter.signal_score >= 70).count()
    return {
        "total_scored": total,
        "high_signal_count": high_signal,
    }


@app.get("/")
def root():
    return {"status": "ok", "service": "civicsignal-api"}
