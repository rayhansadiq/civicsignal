"""
Copy scored matters from one database to another.

Used to move locally-ingested and locally-scored records into the deployed
Neon database without re-running ingestion (which would return different
records on a different day) or re-scoring (which costs LLM quota).

Usage:
    # Source = local Docker Postgres, target = Neon
    set SOURCE_DATABASE_URL=postgresql+psycopg2://civicsignal:civicsignal@localhost:5432/civicsignal
    set TARGET_DATABASE_URL=postgresql+psycopg2://...neon.tech/neondb?sslmode=require
    python migrate_db.py

Safe to re-run: rows already present in the target are skipped, matched on
(source_client, legistar_matter_id).
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, Matter

load_dotenv()

SOURCE_URL = os.getenv("SOURCE_DATABASE_URL")
TARGET_URL = os.getenv("TARGET_DATABASE_URL")

FIELDS = [
    "source_client", "legistar_matter_id", "matter_file", "matter_name",
    "matter_title", "matter_type", "matter_status", "matter_body",
    "intro_date", "agenda_date", "passed_date",
    "signal_score", "signal_category", "signal_summary", "signal_generated_at",
]


def main():
    if not SOURCE_URL or not TARGET_URL:
        raise SystemExit(
            "Set both SOURCE_DATABASE_URL and TARGET_DATABASE_URL.\n"
            "See the docstring at the top of this file for an example."
        )

    if SOURCE_URL == TARGET_URL:
        raise SystemExit("Source and target are the same database. Nothing to do.")

    src_engine = create_engine(SOURCE_URL)
    tgt_engine = create_engine(TARGET_URL, pool_pre_ping=True)

    print("Creating tables in target if they don't exist...")
    Base.metadata.create_all(bind=tgt_engine)

    SrcSession = sessionmaker(bind=src_engine)
    TgtSession = sessionmaker(bind=tgt_engine)
    src, tgt = SrcSession(), TgtSession()

    try:
        rows = src.query(Matter).all()
        print(f"Found {len(rows)} rows in source.")

        # Fetch existing keys in one query rather than one lookup per row.
        existing = {
            (c, m) for c, m in tgt.query(
                Matter.source_client, Matter.legistar_matter_id
            ).all()
        }
        print(f"Target already has {len(existing)} rows.")

        copied = skipped = 0
        for row in rows:
            key = (row.source_client, row.legistar_matter_id)
            if key in existing:
                skipped += 1
                continue
            tgt.add(Matter(**{f: getattr(row, f) for f in FIELDS}))
            copied += 1

        tgt.commit()

        total = tgt.query(Matter).count()
        scored = tgt.query(Matter).filter(Matter.signal_score.isnot(None)).count()
        print(f"\nCopied {copied}, skipped {skipped} already present.")
        print(f"Target now holds {total} rows, {scored} of them scored.")
    except Exception:
        tgt.rollback()
        raise
    finally:
        src.close()
        tgt.close()


if __name__ == "__main__":
    main()
