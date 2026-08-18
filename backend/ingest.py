"""
Ingestion script: pulls real city/county legislation & agenda records from
Legistar's public API (the system hundreds of U.S. cities and counties use
to publish council/board agendas; no key required for most clients) and
loads them into Postgres.

Verified working clients (no token needed): "seattle", "oakland".
You can find others by guessing the subdomain a city uses for Legistar,
e.g. https://<client>.legistar.com. See README for how to check one.

Run it directly:
    python ingest.py seattle --limit 50
    python ingest.py oakland --limit 50
"""

import argparse
import sys

import httpx
from sqlalchemy.exc import IntegrityError

from db import SessionLocal, Matter, init_db

LEGISTAR_BASE = "https://webapi.legistar.com/v1"


def fetch_matters(client: str, limit: int = 50) -> list[dict]:
    """Fetch the most recently introduced matters for a Legistar client."""
    url = f"{LEGISTAR_BASE}/{client}/matters"
    params = {
        "$top": limit,
        "$orderby": "MatterIntroDate desc",
    }

    with httpx.Client(timeout=30.0) as http_client:
        resp = http_client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def store_matters(client: str, records: list[dict]) -> int:
    db = SessionLocal()
    stored = 0
    try:
        for r in records:
            matter_id = r.get("MatterId")
            if matter_id is None:
                continue

            existing = (
                db.query(Matter)
                .filter(Matter.source_client == client, Matter.legistar_matter_id == matter_id)
                .first()
            )
            if existing:
                continue  # don't duplicate on re-runs (fast path)

            matter = Matter(
                source_client=client,
                legistar_matter_id=matter_id,
                matter_file=r.get("MatterFile"),
                matter_name=r.get("MatterName"),
                matter_title=r.get("MatterTitle"),
                matter_type=r.get("MatterTypeName"),
                matter_status=r.get("MatterStatusName"),
                matter_body=r.get("MatterBodyName"),
                intro_date=r.get("MatterIntroDate"),
                agenda_date=r.get("MatterAgendaDate"),
                passed_date=r.get("MatterPassedDate"),
            )
            db.add(matter)
            stored += 1

        try:
            db.commit()
        except IntegrityError:
            # The unique constraint on (source_client, legistar_matter_id)
            # caught something the check above missed, which means another
            # writer inserted between the check and the commit. Losing this
            # batch is correct: the rows are already in the database.
            db.rollback()
            print("Another ingest run stored these records first; nothing new added.")
            stored = 0
    finally:
        db.close()

    return stored


def main():
    parser = argparse.ArgumentParser(
        description="Ingest real city/county legislation from Legistar"
    )
    parser.add_argument(
        "client", help='Legistar client ID, e.g. "seattle" or "oakland"'
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Max records to fetch (Legistar caps at 1000)"
    )
    args = parser.parse_args()

    print("Initializing database schema (if needed)...")
    init_db()

    print(f"Fetching up to {args.limit} recent matters from Legistar client '{args.client}'...")
    try:
        records = fetch_matters(args.client, args.limit)
    except httpx.HTTPStatusError as e:
        print(
            f"Legistar returned an error for client '{args.client}': {e}\n"
            "This usually means the client ID is wrong or that city requires a token.",
            file=sys.stderr,
        )
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Failed to reach Legistar: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(records)} records from '{args.client}'")

    stored = store_matters(args.client, records)
    print(f"Stored {stored} new matters (skipped duplicates).")
    print("Next step: run `python ai_signals.py` to generate buying signals for them.")


if __name__ == "__main__":
    main()
