"""
Turns raw Legistar records into "buying signals" using an LLM.

This is the part of the project that maps most directly to NationGraph's
actual product: taking a messy public agenda item and extracting something
a sales/BD person can act on: a score, a category, and a one-line reason
"why this matters right now."

Provider-agnostic by design: it talks to any OpenAI-compatible chat API.
By default it points at Google's Gemini endpoint (which has a free tier and
speaks the OpenAI protocol), but switching to OpenAI, Groq, or a local
Ollama server is a change to two environment variables, not to this code.

Run after ingest.py:
    python ai_signals.py
    python ai_signals.py --limit 20     # only score 20, to protect free quota
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from db import SessionLocal, Matter

load_dotenv()

# --- Provider config -------------------------------------------------------
# These three values are all that change if you swap LLM providers.
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Gemini's free tier allows roughly 10 requests/minute. We space requests out
# rather than firing them all at once and collecting 429s. Override via .env
# if you move to a paid tier or a local model with no limit.
SECONDS_BETWEEN_REQUESTS = float(os.getenv("LLM_SECONDS_BETWEEN_REQUESTS", "6.5"))

MAX_RETRIES = 3

SYSTEM_PROMPT = """You are an analyst for a company that helps vendors sell software \
and services to public sector organizations (cities, counties, school districts, \
state agencies). Given a single piece of city/county legislation or an agenda item, \
decide whether it represents a useful "buying signal" for a vendor watching this space.

Reply with ONLY a raw JSON object. No markdown, no code fences, no commentary.
Use exactly this shape:
{
  "signal_score": <integer 0-100, how actionable/interesting this is for a vendor>,
  "signal_category": <one of: "renewal", "new_initiative", "expansion", "low_signal">,
  "signal_summary": <one plain-English sentence: why this matters, for a salesperson skimming a list>
}

Guidance:
- High scores (70-100): technology/software contracts, new initiatives or
  modernization efforts, RFPs, or budget items suggesting a city/county is
  actively evaluating or funding a new system or service.
- Medium scores (40-69): general infrastructure, facilities, or service
  contracts that could be relevant to some vendors but aren't clearly tech-related.
- Low scores (0-30): routine administrative matters, appointments, proclamations,
  or items with no real signal for a vendor.
- Be concise and concrete in signal_summary. No fluff, and don't repeat the raw title verbatim.
"""

VALID_CATEGORIES = {"renewal", "new_initiative", "expansion", "low_signal"}


def build_user_prompt(matter: Matter) -> str:
    return json.dumps(
        {
            "city_or_county": matter.source_client,
            "matter_file": matter.matter_file,
            "matter_name": matter.matter_name,
            "matter_title": matter.matter_title,
            "matter_type": matter.matter_type,
            "matter_status": matter.matter_status,
            "matter_body": matter.matter_body,
            "intro_date": matter.intro_date,
        }
    )


def extract_json(raw: str) -> dict:
    """
    Parse the model's reply into a dict.

    Models sometimes wrap JSON in ```json fences or add a stray sentence even
    when told not to, and not every provider supports a strict JSON mode. So
    we try the clean path first, then fall back to pulling out the first
    {...} block we can find.
    """
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences if present
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Last resort: grab the outermost {...}
    braces = re.search(r"\{.*\}", raw, re.DOTALL)
    if braces:
        return json.loads(braces.group(0))

    raise ValueError(f"Could not find JSON in model reply: {raw[:200]!r}")


def validate(result: dict) -> dict:
    """Coerce the model's output into something safe to store."""
    score = int(result.get("signal_score", 0))
    score = max(0, min(100, score))  # clamp to 0-100

    category = str(result.get("signal_category", "low_signal")).strip().lower()
    if category not in VALID_CATEGORIES:
        category = "low_signal"

    summary = str(result.get("signal_summary", "")).strip()

    return {
        "signal_score": score,
        "signal_category": category,
        "signal_summary": summary,
    }


def score_matter(client: OpenAI, matter: Matter) -> dict:
    """Score one matter, retrying with backoff on transient failures."""
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(matter)},
                ],
            )
            raw = response.choices[0].message.content
            return validate(extract_json(raw))
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                backoff = SECONDS_BETWEEN_REQUESTS * attempt
                print(f"      attempt {attempt} failed ({e}); retrying in {backoff:.0f}s")
                time.sleep(backoff)

    raise last_error


def main():
    parser = argparse.ArgumentParser(description="Generate buying signals for ingested matters")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only score this many matters this run (useful on a free-tier daily quota)",
    )
    args = parser.parse_args()

    if not API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key. For the free Google\n"
            "Gemini tier, get one at https://aistudio.google.com/apikey"
        )

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    db = SessionLocal()

    try:
        query = db.query(Matter).filter(Matter.signal_score.is_(None))
        total_pending = query.count()
        pending = query.limit(args.limit).all() if args.limit else query.all()

        print(f"{total_pending} matters have no signal yet; scoring {len(pending)} this run.")
        print(f"Model: {MODEL}  ({SECONDS_BETWEEN_REQUESTS}s between requests)\n")

        succeeded = 0
        failed = 0

        for i, matter in enumerate(pending, start=1):
            try:
                result = score_matter(client, matter)
            except Exception as e:
                failed += 1
                print(f"  [{i}/{len(pending)}] FAILED {matter.matter_file}: {e}")
                continue

            matter.signal_score = result["signal_score"]
            matter.signal_category = result["signal_category"]
            matter.signal_summary = result["signal_summary"]
            matter.signal_generated_at = datetime.now(timezone.utc)
            db.add(matter)
            db.commit()
            succeeded += 1

            print(
                f"  [{i}/{len(pending)}] ({matter.source_client}) {matter.matter_file} -> "
                f"{matter.signal_score:>3} {matter.signal_category}"
            )

            # Stay under the free tier's per-minute cap.
            if i < len(pending):
                time.sleep(SECONDS_BETWEEN_REQUESTS)

        print(f"\nDone. {succeeded} scored, {failed} failed.")
        if total_pending > len(pending):
            print(f"{total_pending - len(pending)} still unscored. Run again to continue.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
