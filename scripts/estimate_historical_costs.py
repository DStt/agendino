"""
One-time script to estimate historical API costs for existing recordings.
Retroactively populates the cost_tracking table with estimated costs.

Usage: python scripts/estimate_historical_costs.py
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Gemini pricing estimates (per 1M tokens)
GEMINI_INPUT_RATE = 0.075 / 1_000_000
GEMINI_OUTPUT_RATE = 0.30 / 1_000_000

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def main():
    db_name = os.getenv("DATABASE_NAME", "agendino.db")
    db_path = os.path.join(os.path.dirname(__file__), "..", "settings", db_name)

    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    recordings = conn.execute(
        "SELECT id, name, transcript, duration FROM recording WHERE transcript IS NOT NULL AND transcript != ''"
    ).fetchall()

    print(f"Found {len(recordings)} recordings with transcripts")

    inserted = 0
    skipped = 0

    for rec in recordings:
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM cost_tracking WHERE recording_id = ?", (rec["id"],)
        ).fetchone()

        if existing["cnt"] > 0:
            skipped += 1
            continue

        transcript = rec["transcript"]
        input_tokens = estimate_tokens(transcript)
        transcription_cost = input_tokens * GEMINI_INPUT_RATE

        conn.execute(
            """INSERT INTO cost_tracking
               (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
               VALUES (?, 'transcription', 'gemini', 'gemini-flash', ?, 0, ?, 1)""",
            (rec["id"], input_tokens, round(transcription_cost, 6)),
        )
        inserted += 1

        summaries = conn.execute(
            "SELECT id, summary FROM summary WHERE recording_id = ?", (rec["id"],)
        ).fetchall()

        for s in summaries:
            if not s["summary"]:
                continue
            in_tokens = estimate_tokens(transcript)
            out_tokens = estimate_tokens(s["summary"])
            cost = (in_tokens * GEMINI_INPUT_RATE) + (out_tokens * GEMINI_OUTPUT_RATE)

            conn.execute(
                """INSERT INTO cost_tracking
                   (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
                   VALUES (?, 'summarization', 'gemini', 'gemini-flash', ?, ?, ?, 1)""",
                (rec["id"], in_tokens, out_tokens, round(cost, 6)),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"Done. Inserted {inserted} estimated cost entries, skipped {skipped} recordings (already had data).")


if __name__ == "__main__":
    main()
