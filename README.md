# CivicSignal

A full-stack project that pulls real city/county legislation data and uses
an LLM to turn it into "buying signals": a scored, categorized, plain
English summary of why a given piece of legislation might matter to a
vendor selling into government. Built as a portfolio project for a
NationGraph software engineering internship application.

**Status: Stage 2. Backend and dashboard both working.**

## Why this project

NationGraph's product turns millions of public-sector sources into buying
signals for companies selling to cities, counties, states, schools, and
special districts. This project is a small, honest version of that same
idea, using a real public data source:

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
│   ├── main.py            # FastAPI: /api/signals, /api/stats
│   ├── ingest.py          # Pulls real legislation from Legistar
│   ├── ai_signals.py      # Scores + summarizes matters with an LLM
│   ├── db.py              # SQLAlchemy models + session
│   └── requirements.txt
├── frontend/
│   ├── app/               # Next.js App Router pages + Redux provider
│   ├── components/        # Table, filters, badges, detail panel
│   ├── lib/               # Typed API client + shared types
│   └── store/             # Redux Toolkit slice
└── docker-compose.yml     # Postgres
```

## Engineering notes

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
- Five shadcn primitives (`card`, `badge`, `dialog`, `input`, `select`) are
  installed but unused; the filters and badges are hand-rolled.

## Running it

### 1. Start Postgres

Requires Docker Desktop installed and running.

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
venv\Scripts\activate        # on Windows (use `source venv/bin/activate` on Mac/Linux)
pip install -r requirements.txt
copy .env.example .env       # on Windows (use `cp .env.example .env` on Mac/Linux)
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
copy .env.local.example .env.local    # cp on Mac/Linux
npm run dev
```

Open `http://localhost:3000`.

### Trying other cities

Legistar client IDs come from a city's Legistar subdomain, e.g.
`https://seattle.legistar.com` → client ID `seattle`. To check whether a
city's data is public before ingesting it, visit this URL in your browser:

```
https://webapi.legistar.com/v1/<client>/matters?$top=1
```

If that returns JSON (not an error), it works.

## What's next

- Deploy: Vercel for the frontend, Neon for Postgres, Render for the API
- Handle free-tier cold starts in the UI without reporting a false error
- Ingest more cities so the dataset reflects the scale of the problem
- Test coverage for the JSON parsing and score validation

## A note on data

Legistar captures official city/county legislative records: introduced
ordinances, resolutions, reports, and agenda items. That is a close
match to what NationGraph actually watches (city council and county board
activity).
