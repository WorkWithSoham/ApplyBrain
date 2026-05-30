"""
AutoApply Brain — Personal AI Job Application Engine
Runs on port 8083, calls Smart AI Router for all LLM tasks.
"""

import os
import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from scorer import score_fit

db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=2, max_size=5
    )
    yield
    await db_pool.close()

app = FastAPI(title="AutoApply Brain", lifespan=lifespan)

# ── Models ────────────────────────────────────────────────────────────────────

class FitRequest(BaseModel):
    resume_text: str
    jd_text:     str
    company:     str
    role:        str

class FitResponse(BaseModel):
    fit_score:        int
    matched_keywords: list[str]
    missing_keywords: list[str]
    analysis:         str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/score", response_model=FitResponse)
async def score(req: FitRequest):
    """Score how well your resume matches a job description."""
    result = await score_fit(req.resume_text, req.jd_text)

    # Save to database
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO applications
                (company, role, jd_text, fit_score,
                 missing_keywords, matched_keywords)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            req.company,
            req.role,
            req.jd_text,
            result["fit_score"],
            result["missing_keywords"],
            result["matched_keywords"],
        )

    return FitResponse(**result)

@app.get("/applications")
async def get_applications():
    """Get all tracked applications."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, company, role, fit_score,
                   matched_keywords, missing_keywords,
                   status, applied_at
            FROM applications
            ORDER BY applied_at DESC
        """)
    return [dict(r) for r in rows]

@app.get("/health")
async def health():
    return {"status": "ok"}