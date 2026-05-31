"""
AutoApply Brain — Personal AI Job Application Engine
Runs on port 8083, calls Smart AI Router for all LLM tasks.
"""

import os
import asyncpg
import PyPDF2
import io
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    jd_text: str
    company: str
    role: str


class FitResponse(BaseModel):
    fit_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    analysis: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.post("/score", response_model=FitResponse)
async def score(
    resume_text: str = Form(...),
    jd_text: str = Form(...),
    company: str = Form(...),
    role: str = Form(...),
):
    """Score fit — accepts form fields so line breaks are handled automatically."""
    resume_clean = " ".join(resume_text.split())
    jd_clean = " ".join(jd_text.split())

    result = await score_fit(resume_clean, jd_clean)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO applications
                (company, role, jd_text, fit_score,
                 missing_keywords, matched_keywords)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            company,
            role,
            jd_clean,
            result["fit_score"],
            result["missing_keywords"],
            result["matched_keywords"],
        )

    return FitResponse(**result)


@app.post("/score/pdf", response_model=FitResponse)
async def score_pdf(
    resume_pdf: UploadFile = File(...),
    jd_text: str = Form(...),
    company: str = Form(...),
    role: str = Form(...),
):
    """Score fit using a PDF resume upload instead of pasted text."""

    # Extract text from PDF
    try:
        pdf_bytes = await resume_pdf.read()
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        resume_text = " ".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
        resume_text = " ".join(resume_text.split())  # clean whitespace
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {e}")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    # Clean JD text too
    jd_clean = " ".join(jd_text.split())

    result = await score_fit(resume_text, jd_clean)

    # Save to database
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO applications
                (company, role, jd_text, fit_score,
                 missing_keywords, matched_keywords)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            company,
            role,
            jd_clean,
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
