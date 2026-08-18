# CivicSignal

**Live: https://civicsignal-coral.vercel.app**

A full-stack project that pulls real city/county legislation data and uses
an LLM to turn it into "buying signals": a scored, categorized, plain
English summary of why a given piece of legislation might matter to a
vendor selling into government.

> The API runs on a free tier that sleeps after 15 minutes idle. The first
> load may take up to a minute while it wakes; the UI shows a waking state
> rather than an error while that happens.

## A real result

The highest-scoring record the pipeline found, unedited:

> **90 / Renewal** - Oakland is authorizing a two-year, $1.08 million
> cooperative contract renewal with NEOGOV for HRIS subscription services.

A named incumbent vendor, a dollar figure, and a renewal window, extracted
from a council agenda nobody was reading. That is the product in one row.

## Why this project

Companies that sell to government have a discovery problem. The signals are
public by law: every contract renewal, every new initiative, every budget
line is published in a council agenda. But they are spread across thousands
of cities, counties, school districts, and special districts, written in
procedural language, and buried in documents nobody reads. By the time a
vendor hears about a renewal, it has usually already been decided.

This project is a small, honest version of the tool that fixes that, built
on a real public data source:

1. **Ingest** real legislation and agenda data from **Legistar**, the
   platform hundreds of U.S. cities and counties actually use to publish
   council/board agendas (Seattle, Oakland, and many others). No API key
   required.
2. **Enrich** each record with an LLM that scores it, categorizes it
   (renewal / new initiative / expansion / low signal), and writes a
   one-sentence "why this matters" summary.
3. **Surface** it in a dashboard a salesperson could actually use.

## What the data says

100 records ingested from Seattle and Oakland, all scored:

| | Count |
|---|---|
| Low signal (<40) | 87 |
| Medium (40-69) | 11 |
| **High (70+)** | **2** |

**87% of it is noise**: appointments, meeting minutes, procedural referrals.
That ratio is the entire argument for the product: a vendor cannot read 100
agenda items to find the two worth acting on, let alone the millions published
across every city, county, and school district in the country.

## Project structure

```
civicsignal/
├── backend/
│   ├── main.py            # FastAPI: /health, /api/signals, /api/clients, /api/stats
│   ├── ingest.py          # Pulls real legislation from Legistar
│   ├── ai_signals.py      # Scores + summarizes matters with an LLM
│   ├── db.py              # SQLAlchemy model + session
│   ├── migrate_db.py      # Copies rows between databases (local -> Neon)
│   ├── sql/indexes.sql    # Brings an existing database up to date with the model
│   ├── tests/             # pytest: parsing, validation, endpoints, CORS
│   └── requirements.txt
├── frontend/
│   ├── app/               # Next.js App Router pages + Redux provider
│   ├── components/        # Table, filters, badges, detail panel
│   ├── lib/               # Typed API client + shared types
│   └── store/             # Redux Toolkit slice
└── docker-compose.yml     # Postgres
```

## Architecture

| Layer | Service | Why |
|---|---|---|
| Frontend | Vercel | Free, auto-deploys from GitHub, built by the Next.js team |
| API | Render | Free Python hosting, 750 instance-hours/month |
| Database | Neon (Postgres) | Free plan is permanent and needs no card |

**Render's own free Postgres was rejected**: it is deleted after 30 days,
which would silently break the demo about a month after deployment. Neon's
free tier persists.

Ingestion and LLM scoring run as local operator scripts against the
deployed database, not in the request path. That is a deliberate limitation
rather than an oversight; scheduling them is listed under What's next.

## Engineering notes

### Cold starts are handled as a state, not an error

Render's free tier sleeps after 15 minutes idle and takes about a minute to
wake. A naive client treats the first failed request as an outage, so the
first visitor of the day is told the site is broken while it is in fact
starting up.

`lib/api.ts` retries with capped exponential backoff for up to 90 seconds and
reports progress through an `onRetry` callback, so the UI can show "waking
up" with a live counter. Two distinctions do the real work:

- **4xx fails immediately.** Retrying will not fix a malformed query.
- **5xx and network failures retry.** That is what a platform returns while
  a service boots.

`ApiUnreachableError` is separate from `ApiError` because "nothing answered"
and "the server said no" are different problems and deserve different copy.

`/health` deliberately does not touch the database. A health check that
queries Postgres reports the service as down whenever Neon is merely asleep,
which would make the platform restart a perfectly healthy process.

### CORS is scoped, including preview deployments

Vercel gives every deployment and every preview branch its own hostname, so
an exact allowlist is unmaintainable. The API accepts a regex:

```
^https://civicsignal[a-z0-9-]*\.vercel\.app$
```

Anchored at both ends on purpose. An unanchored pattern would also match
`https://evil.com/?x=civicsignal-a.vercel.app` and
`https://civicsignal-x.vercel.app.evil.com`, which is the standard way
origin checks get bypassed. Tested against both.

Not `allow_origins=["*"]`. The data is public today, but a wildcard is a
habit that becomes a real problem the moment an endpoint stops being public.

### The LLM layer is provider-agnostic

`ai_signals.py` talks to any OpenAI-compatible chat API. Swapping between
Google Gemini, OpenAI, Groq, or a local Ollama model is three lines in `.env`,
with no code change. Examples for each are in `backend/.env.example`.

Two consequences worth knowing:

- Gemini's OpenAI-compatibility layer doesn't document `response_format`, so
  rather than relying on a strict JSON mode that may not exist,
  `extract_json()` parses defensively (handling markdown fences and chatty
  preambles) and `validate()` clamps the score to 0-100 and falls back to
  `low_signal` on an unrecognized category.
- The free tier allows ~10 requests/minute, so the script paces itself and
  retries with backoff. `--limit N` caps a run to protect a daily quota.

### Indexes chosen by measurement, not by intuition

The dataset here is 100 rows, where every query is instant and every index
looks unnecessary. So rather than guess at what would matter at the scale
this models, I seeded a local Postgres with **200,000 rows** across 40
cities and measured.

Median of 15 to 25 requests, end to end over HTTP:

| Request | No indexes | B-tree | + trigram |
|---|---|---|---|
| Default list | 47.7ms | 10.3ms | 10.3ms |
| Category filter | 43.5ms | 10.5ms | 10.6ms |
| City filter | 26.1ms | 11.6ms | - |
| `min_score` filter | 41.1ms | 13.3ms | - |
| Search, common term | 189ms | 11.6ms | 11.7ms |
| Search, no match | 178ms | 184ms | **6.5ms** |

Three things came out of this that I would not have predicted:

**The sort was the bottleneck, not the filters.** Every response ends in
`ORDER BY signal_score DESC LIMIT n`, so returning 100 rows meant reading and
sorting all 200,000. An index on the sort column turns that into an index
scan that stops at the limit: 57ms to 0.14ms at the query level, and 47.7ms
to 10.3ms end to end. The gap between those two numbers is the useful part.
The remaining 10ms is JSON serialization and HTTP, so further database
tuning would buy nothing.

**Search was already fixed, except when it wasn't.** With the score index in
place, a search for a common term is fast without any text index, because
Postgres walks the index in score order and stops once it has 100 matches. A
search that matches *nothing* has no early exit, so it reads every row: 184ms.
Trigram indexes fix that specific case, 28x. Users search for the unusual
thing, so the slow path is the common one.

**Two indexes were pure cost.** `index=True` on the primary key built a second
index identical to the one the primary key already maintains, and nothing ever
looked up `legistar_matter_id` on its own. Together they were 8.8MB of write
overhead buying nothing. Removing them left the API measurably faster to
write to and identical to read from.

`/api/stats` also went from two `COUNT` queries to one filtered aggregate.
That barely registers locally, but the database is on Neon and the API is on
Render, so the saving is a network round trip rather than CPU.

### create_all does not migrate

Worth stating plainly, because it cost me a confusing benchmark run:
SQLAlchemy's `create_all()` checks whether each *table* exists and skips it
entirely if it does. It never compares the existing table against the model.
So an index or constraint added after a table was first created is silently
never built.

A fresh database gets everything. A database that already has `matters` gets
nothing. `backend/sql/indexes.sql` exists to close that gap by hand, and is
idempotent so it can be re-run safely:

```bash
psql "$DATABASE_URL" -f sql/indexes.sql
```

This is what a migration tool is for, and a production project would use
Alembic instead of a hand-maintained SQL file.

### Tests target the code most likely to be silently wrong

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests/ -q          # 70 tests
```

The suite concentrates on `extract_json()` and `validate()`, the two
functions standing between an LLM's output and the database. Everything
else in the pipeline fails loudly: a bad request 500s, a broken query
raises. A bad parse or an unclamped score writes plausible-looking wrong
data that then appears in the dashboard as fact. So those get the hard
cases: markdown fences, chatty preambles, nested objects, a score of 150,
a category the model invented.

`conftest.py` points `DATABASE_URL` at a throwaway SQLite file *before*
importing `db`, which reads it at import time. Without that ordering the
suite would run against the deployed database. It works because
`load_dotenv()` does not override variables that are already set.

Two tests exist purely to protect decisions that are easy to undo by
accident: one monkeypatches the session factory to raise and asserts
`/health` still returns 200, and one fires twelve origins at the CORS
regex, including a suffix attack and an unanchored-prefix attack.

### Redux and react-window are deliberately oversized

With ~100 rows, `useState` and a plain `<table>` would do the job. Both are
here because the dataset this models is millions of public-sector records,
where centralized filter state and virtualization stop being optional.

Redux holds **only filter and selection state**, not the fetched signals.
Caching server data in Redux means writing your own invalidation, so the
signals live in component state and refetch when filters change.

The list renders roughly 12 rows at a time regardless of how many match.

Note: `react-window` v2 has a different API from v1. It takes a
`rowComponent` plus `rowProps` rather than v1's children-as-render-prop.
Most tutorials online still show v1 and won't compile against v2.

## Known limitations

- `GET /api/clients` returns the distinct cities, but the frontend filter
  still reads a hardcoded list in `lib/types.ts`. Wiring it to the endpoint
  is a pending cleanup.
- The API caps `limit` at 200, and there's no pagination. Fine at 100 records;
  the first thing to fix before ingesting many more cities.
- Ingestion runs as a manual operator script rather than on a schedule.
- Only two cities. The product argument is about scale, and two cities
  gesture at it rather than demonstrate it.
- The unique constraint and the indexes were added after the deployed table
  was created. They exist in the model and in any fresh database, but the
  deployed Neon table needs `sql/indexes.sql` run against it once, because
  `create_all` does not alter existing tables. There is no migration tool
  here; a real project would use Alembic.
- The benchmark numbers above come from synthetic rows on local Postgres.
  They show the shape of the problem honestly, but a managed database over a
  network will not reproduce them exactly.

## Running it

### 1. Start Postgres

Requires Docker Desktop installed and running.

```bash
docker compose up -d
```

### 2. Backend

On Mac/Linux:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows (PowerShell):

```powershell
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and set `LLM_API_KEY`. The default provider is **Google
Gemini's free tier**. Grab a key (no credit card needed) at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey).

The LLM layer is provider-agnostic: it talks to any OpenAI-compatible API, so
switching to OpenAI, Groq, or a local Ollama model means changing `LLM_BASE_URL`
and `LLM_MODEL` in `.env`, with no code changes. Examples are in `.env.example`.

```bash
# Pull real legislation data. These two clients are verified working, no token needed
python ingest.py seattle --limit 50
python ingest.py oakland --limit 50

# Turn the raw records into buying signals.
# Note: the free tier is ~10 requests/min, so this paces itself.
# 50 records takes about 5 minutes. Use --limit 20 to score fewer.
python ai_signals.py

# Start the API
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/api/signals` in your browser. You should see
real Seattle/Oakland legislation, each with an AI-generated signal_score,
signal_category, and signal_summary.

### 3. Frontend

In a second terminal, with the backend still running:

```bash
cd frontend
npm install
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API. To point it
somewhere else, create `frontend/.env.local` with a single line:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Open `http://localhost:3000`.

### Trying other cities

Legistar client IDs come from a city's Legistar subdomain, e.g.
`https://seattle.legistar.com` gives the client ID `seattle`. To check whether a
city's data is public before ingesting it, visit this URL in your browser:

```
https://webapi.legistar.com/v1/<client>/matters?$top=1
```

If that returns JSON (not an error), it works.

## What's next

- Ingest more cities so the dataset reflects the scale of the problem
- Schedule ingestion instead of running it by hand
- Pagination, needed before the dataset outgrows the 200-record cap
- Alembic migrations, so a schema change does not need a hand-written
  `ALTER TABLE` against the deployed database
