"""
Database setup for CivicSignal.

One table, on purpose: `matters` holds a raw Legistar record (a piece of
city/county legislation or agenda item) plus the AI-derived "buying signal"
fields once ai_signals.py has processed it. Simple enough to explain end to
end in an interview, structured the way a real signal product would need.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://civicsignal:civicsignal@localhost:5432/civicsignal",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Matter(Base):
    """A single piece of city/county legislation or agenda item from Legistar."""

    __tablename__ = "matters"

    # ingest.py checks for an existing row before inserting, but a check-then-
    # insert is only as good as the assumption that nothing else is writing.
    # Two ingest runs at once, or one retried after a timeout, would both pass
    # the check and both insert. Stating the rule in the schema means the
    # database enforces it no matter who is writing or how many of them there
    # are, instead of it living in a comment and a hopeful query.
    __table_args__ = (
        UniqueConstraint(
            "source_client", "legistar_matter_id", name="uq_matter_client_legistar_id"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Which city/county this came from, and Legistar's own ID for it.
    # The same MatterId can repeat across different cities, so neither column
    # identifies a record on its own; the pair does.
    source_client = Column(String, index=True)       # e.g. "seattle", "oakland"
    legistar_matter_id = Column(Integer, index=True)

    # Raw fields from Legistar (public data)
    matter_file = Column(String)          # e.g. "CB 118329", the file/bill number
    matter_name = Column(String)          # short name
    matter_title = Column(Text)           # full descriptive title, the main text we score
    matter_type = Column(String)          # e.g. "Ordinance", "Resolution", "Report"
    matter_status = Column(String)        # e.g. "Passed", "In Committee"
    matter_body = Column(String)          # e.g. which committee/council body
    intro_date = Column(String)
    agenda_date = Column(String)
    passed_date = Column(String)

    # AI-derived "buying signal" fields
    signal_score = Column(Integer)          # 0-100, how actionable/interesting this is
    signal_category = Column(String)        # e.g. "renewal", "new_initiative", "expansion", "low_signal"
    signal_summary = Column(Text)           # plain-English "why this matters" blurb
    signal_generated_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
