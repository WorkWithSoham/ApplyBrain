"""
Layer 3: Feedback Engine
- Scores recent LLM responses on quality heuristics + latency
- Runs nightly via APScheduler to update routing_weights in PostgreSQL
- Exposes /metrics endpoint for Prometheus to scrape
"""

import os
import asyncio
import asyncpg
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── App lifecycle ─────────────────────────────────────────────────────────

db_pool = None
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=2, max_size=5)

    # Score new responses every 10 minutes
    scheduler.add_job(score_recent_responses, "interval", minutes=10)
    # Update routing weights every night at 2 AM
    scheduler.add_job(update_routing_weights, "cron", hour=2, minute=0)
    scheduler.start()

    yield

    scheduler.shutdown()
    await db_pool.close()

app = FastAPI(title="Feedback Engine", lifespan=lifespan)

# ─── Scoring ───────────────────────────────────────────────────────────────

def heuristic_quality_score(response_text: str, latency_ms: int) -> float:
    """
    Simple heuristic scorer (no LLM needed, zero cost).
    Returns a score between 0.0 and 1.0.

    Upgrade path: replace with an LLM-as-judge call using Gemini free tier,
    or collect explicit user thumbs-up/down and use those as ground truth.
    """
    score = 1.0

    # Penalise very short responses (likely truncated or refused)
    if len(response_text) < 20:
        score -= 0.4
    elif len(response_text) < 50:
        score -= 0.2

    # Penalise slow responses
    if latency_ms > 30_000:
        score -= 0.3
    elif latency_ms > 15_000:
        score -= 0.15
    elif latency_ms > 5_000:
        score -= 0.05

    # Penalise refusal indicators
    refusal_phrases = ["i cannot", "i'm unable", "i can't", "as an ai", "i don't have access"]
    if any(p in response_text.lower() for p in refusal_phrases):
        score -= 0.3

    # Reward structured, detailed responses
    if len(response_text) > 200:
        score += 0.05
    if "\n" in response_text:  # multi-line = likely structured
        score += 0.05

    return max(0.0, min(1.0, score))


async def score_recent_responses():
    """Score all request_log rows that don't yet have a response_scores entry."""
    log.info("Scoring recent responses...")
    async with db_pool.acquire() as conn:
        unscored = await conn.fetch("""
            SELECT rl.request_id, rl.model_used, rl.response_text, rl.latency_ms
            FROM request_log rl
            LEFT JOIN response_scores rs ON rl.request_id = rs.request_id
            WHERE rs.request_id IS NULL
              AND rl.created_at > NOW() - INTERVAL '24 hours'
            LIMIT 500
        """)

        for row in unscored:
            score = heuristic_quality_score(row["response_text"] or "", row["latency_ms"] or 99999)
            await conn.execute("""
                INSERT INTO response_scores (request_id, model_name, latency_ms, quality_score)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, row["request_id"], row["model_used"], row["latency_ms"], score)

    log.info(f"Scored {len(unscored)} responses.")


# ─── Weight update ─────────────────────────────────────────────────────────

async def update_routing_weights():
    """
    Nightly job: recompute routing_weights from the last 7 days of scores.

    Formula: new_weight = avg(quality_score) * speed_bonus
    where speed_bonus = 1.2 if avg_latency < 3s, 0.8 if > 15s, else 1.0
    """
    log.info("Updating routing weights...")
    async with db_pool.acquire() as conn:
        # Aggregate scores per model over last 7 days
        model_stats = await conn.fetch("""
            SELECT
                rs.model_name,
                rl.task_type,
                AVG(rs.quality_score)  AS avg_quality,
                AVG(rs.latency_ms)     AS avg_latency_ms,
                COUNT(*)               AS sample_count
            FROM response_scores rs
            JOIN request_log rl ON rs.request_id = rl.request_id
            WHERE rs.scored_at > NOW() - INTERVAL '7 days'
            GROUP BY rs.model_name, rl.task_type
            HAVING COUNT(*) >= 5         -- only update if we have enough data
        """)

        for row in model_stats:
            avg_latency = row["avg_latency_ms"] or 10_000
            if avg_latency < 3_000:
                speed_bonus = 1.2
            elif avg_latency > 15_000:
                speed_bonus = 0.8
            else:
                speed_bonus = 1.0

            new_weight = round(float(row["avg_quality"]) * speed_bonus, 4)

            await conn.execute("""
                INSERT INTO routing_weights (task_type, model_name, weight, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (task_type, model_name)
                DO UPDATE SET weight = $3, updated_at = NOW()
            """, row["task_type"], row["model_name"], new_weight)

            log.info(
                f"Updated weight: task={row['task_type']} model={row['model_name']} "
                f"weight={new_weight} (n={row['sample_count']})"
            )

    log.info("Routing weights updated.")


# ─── Metrics endpoint ──────────────────────────────────────────────────────

@app.get("/metrics/weights")
async def get_weights():
    """Returns current routing weights — useful for the Grafana dashboard."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT task_type, model_name, weight, updated_at FROM routing_weights ORDER BY task_type, weight DESC")
    return [dict(r) for r in rows]


@app.get("/metrics/scores/summary")
async def score_summary():
    """Returns avg quality + latency per model for the last 24h."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT model_name,
                   ROUND(AVG(quality_score)::numeric, 3) AS avg_quality,
                   ROUND(AVG(latency_ms)::numeric, 0)    AS avg_latency_ms,
                   COUNT(*) AS requests
            FROM response_scores
            WHERE scored_at > NOW() - INTERVAL '24 hours'
            GROUP BY model_name
            ORDER BY avg_quality DESC
        """)
    return [dict(r) for r in rows]


@app.post("/trigger/score")
async def trigger_score():
    """Manually trigger scoring — useful during development."""
    await score_recent_responses()
    return {"status": "ok"}


@app.post("/trigger/update-weights")
async def trigger_update():
    """Manually trigger weight update — useful during development."""
    await update_routing_weights()
    return {"status": "ok"}
