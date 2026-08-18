"""
Shared test setup.

The critical job here is pointing DATABASE_URL at a throwaway SQLite file
BEFORE db.py is imported. db.py reads the variable at import time, and the
real .env holds the production Neon URL, so without this the suite would run
against live data. `load_dotenv()` does not override variables that are
already set, which is what makes this work.
"""

import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "tests" / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,https://example.com"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import db as dbmod  # noqa: E402
import main  # noqa: E402


# (source_client, legistar_matter_id, matter_file, title, category, score)
SEED = [
    ("oakland", 1, "26-0893", "Cooperative contract renewal with NEOGOV for HRIS", "renewal", 90),
    ("oakland", 2, "26-0876", "Reimbursement resolution for general obligation bonds", "new_initiative", 75),
    ("oakland", 3, "26-0881", "Regional grant governance MOU through 2030", "expansion", 65),
    ("seattle", 4, "Inf 2937", "King County Regional Homelessness Authority transition", "expansion", 55),
    ("seattle", 5, "Inf 2941", "Vehicle Resident Assistance Program draft legislation", "new_initiative", 55),
    ("seattle", 6, "Appt 03595", "Appointment to the citizen advisory board", "low_signal", 0),
    ("seattle", 7, "Min 579", "Meeting minutes", "low_signal", 10),
]


@pytest.fixture(scope="session", autouse=True)
def _database():
    TEST_DB.unlink(missing_ok=True)
    dbmod.Base.metadata.create_all(bind=dbmod.engine)

    session = dbmod.SessionLocal()
    for client, mid, file, title, category, score in SEED:
        session.add(
            dbmod.Matter(
                source_client=client,
                legistar_matter_id=mid,
                matter_file=file,
                matter_title=title,
                matter_type="Ordinance",
                matter_status="Passed",
                matter_body="City Council",
                intro_date="2026-08-10",
                signal_score=score,
                signal_category=category,
                signal_summary=f"Why {file} matters.",
            )
        )
    # One unscored row: endpoints must exclude it, since a record without a
    # signal is not something the dashboard should ever show.
    session.add(
        dbmod.Matter(
            source_client="oakland",
            legistar_matter_id=999,
            matter_file="26-9999",
            matter_title="Ingested but not yet scored",
        )
    )
    session.commit()
    session.close()

    yield

    dbmod.engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client():
    return TestClient(main.app)
