-- Bring an EXISTING database up to date with the current model.
--
--     psql "$DATABASE_URL" -f sql/indexes.sql
--
-- Why this file has to exist:
--
-- init_db() calls SQLAlchemy's create_all(), which checks whether each TABLE
-- exists and skips it entirely if it does. It does not compare the table it
-- found against the model, so an index or constraint added after the table
-- was first created never gets built. A fresh database gets everything; a
-- database that already has `matters` gets nothing.
--
-- That is a real gap, not a quirk to work around, and it is the reason
-- production projects use a migration tool. Alembic would replace this file.
--
-- Everything here is idempotent, so running it twice is harmless.


-- --------------------------------------------------------------------------
-- 1. Uniqueness (also declared in db.py)
-- --------------------------------------------------------------------------
-- ingest.py checks before inserting, but check-then-insert races. This makes
-- the database the thing that enforces it.
--
-- ALTER TABLE ... ADD CONSTRAINT has no IF NOT EXISTS, so it is wrapped to
-- keep the whole file safe to re-run.

DO $$
BEGIN
    ALTER TABLE matters
        ADD CONSTRAINT uq_matter_client_legistar_id
        UNIQUE (source_client, legistar_matter_id);
EXCEPTION
    WHEN duplicate_table THEN
        RAISE NOTICE 'constraint uq_matter_client_legistar_id already exists, skipping';
END $$;


-- --------------------------------------------------------------------------
-- 2. Sort and filter indexes (also declared in db.py)
-- --------------------------------------------------------------------------
-- Every /api/signals response ends in ORDER BY signal_score DESC LIMIT n.
-- Without an index on the sort column, answering with 100 rows means reading
-- and sorting all of them. Measured end to end over HTTP on 200,000 rows:
--
--     default list        47.7ms -> 10.3ms
--     category filter     43.5ms -> 10.5ms
--     city filter         26.1ms -> 11.6ms
--     min_score filter    41.1ms -> 13.3ms
--
-- The remaining ~10ms is JSON serialization and HTTP, not the database.

CREATE INDEX IF NOT EXISTS ix_matters_score_desc
    ON matters (signal_score DESC);

CREATE INDEX IF NOT EXISTS ix_matters_cat_score
    ON matters (signal_category, signal_score DESC);

CREATE INDEX IF NOT EXISTS ix_matters_client_score
    ON matters (source_client, signal_score DESC);


-- --------------------------------------------------------------------------
-- 3. Trigram search (Postgres only, cannot live in db.py)
-- --------------------------------------------------------------------------
-- The search box compiles to ILIKE '%term%'. A leading wildcard makes an
-- ordinary B-tree useless, because a B-tree can only seek on a known prefix.
--
-- For a COMMON term that does not matter. The query still ends in ORDER BY
-- signal_score DESC LIMIT 100, so Postgres walks ix_matters_score_desc in
-- order, tests each row, and stops as soon as it has 100 matches: 11.6ms.
--
-- For a term that matches nothing there is no early exit, so proving it means
-- reading every row: 184ms. With trigram indexes Postgres switches plans and
-- answers in 6.5ms, a 28x difference on exactly the searches people are most
-- likely to type, since users search for the unusual thing.
--
-- Measured cost: index size grows from 19MB to 41MB on a 78MB table, and
-- writes get slower. Ingest runs a few times a day and search is interactive,
-- so that trade is easy. Verified that adding these does NOT regress the
-- common-term or unfiltered cases; the planner keeps the score-index plan.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_matters_title_trgm
    ON matters USING gin (matter_title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_matters_file_trgm
    ON matters USING gin (matter_file gin_trgm_ops);


-- The planner only picks a new index once it has statistics for it.
ANALYZE matters;
