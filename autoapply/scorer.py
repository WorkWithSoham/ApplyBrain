"""
JD Fit Scorer
Scores how well a resume matches a job description.
Uses phi3 via the Smart AI Router — fast and lightweight.
"""

import httpx
import re
from collections import Counter

ROUTER_URL = "http://router:8081/route"

# Common words to ignore when extracting keywords
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "that",
    "this",
    "are",
    "you",
    "will",
    "have",
    "from",
    "our",
    "your",
    "we",
    "in",
    "to",
    "a",
    "an",
    "of",
    "is",
    "be",
    "as",
    "at",
    "by",
    "or",
    "on",
    "it",
    "its",
    "not",
    "but",
    "can",
    "all",
    "has",
    "was",
    "they",
    "across",
    "between",
    "including",
    "seamlessly",
    "within",
    "which",
    "their",
    "there",
    "these",
    "those",
    "would",
    "should",
    "could",
    "about",
    "more",
    "also",
    "into",
    "than",
    "when",
    "both",
    "each",
    "over",
    "such",
    "even",
    "most",
    "other",
    "work",
    "using",
    "make",
    "well",
    "need",
    "good",
    "get",
    "active",
    "activities",
    "amazing",
    "aspects",
    "better",
    "beyond",
    "chance",
    "closely",
    "centrally",
    "building",
    "advanced",
    "build",
    "built",
    "use",
    "used",
    "users",
    "ensure",
    "focus",
    "help",
    "jump",
    "love",
    "plan",
    "reach",
    "remain",
    "running",
    "send",
    "share",
    "ship",
    "trigger",
    "want",
    "work",
    "today",
    "began",
    "born",
    "same",
    "one",
    "full",
    "half",
    "last",
    "next",
    "new",
    "own",
    "top",
    "two",
}

# Tech keywords to specifically look for
TECH_KEYWORDS = {
    "agentic",
    "agents",
    "agent",
    "rust",
    "wasm",
    "golang",
    "opengl",
    "webgl",
    "shell",
    "terminal",
    "orchestration",
    "parallel",
    "prototype",
    "mentor",
    "collaborate",
    "deploy",
    "debug",
    "workflow",
    "workbench",
    "programmatic",
    "security",
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "angular",
    "fastapi",
    "spring",
    "django",
    "node",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "llm",
    "ai",
    "ml",
    "rag",
    "vector",
    "chromadb",
    "kafka",
    "spark",
    "microservices",
    "rest",
    "api",
    "graphql",
    "ci/cd",
    "git",
    "agile",
    "scrum",
    "devops",
    "linux",
    "sql",
    "nosql",
}


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    text = text.lower()
    # Extract words and common tech phrases
    words = set(re.findall(r"\b[a-z][a-z0-9\+\#\.]*\b", text))
    # Keep tech keywords and longer meaningful words
    return {
        w
        for w in words
        if w not in STOPWORDS
        and (w in TECH_KEYWORDS or len(w) > 6)  # raised from 5 to 6
        and not w.isdigit()
    }


async def score_fit(resume_text: str, jd_text: str) -> dict:
    """
    Score how well resume matches JD.
    Returns score, matched keywords, missing keywords,
    and LLM analysis.
    """
    # Step 1: Keyword analysis (no LLM needed — fast)
    resume_keywords = extract_keywords(resume_text)
    jd_keywords = extract_keywords(jd_text)

    matched = resume_keywords & jd_keywords
    missing = jd_keywords - resume_keywords
    score = int((len(matched) / max(len(jd_keywords), 1)) * 100)

    # Step 2: LLM analysis via router (phi3 — fast)
    prompt = f"""Analyze this job application fit in 3 bullet points.
Be specific and concise.

JOB DESCRIPTION (key parts):
{jd_text[:800]}

RESUME SUMMARY:
{resume_text[:600]}

Respond with exactly 3 lines starting with:
STRENGTH: [what matches well]
GAP: [most important missing skill]
ADVICE: [one specific thing to emphasize]"""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                ROUTER_URL,
                json={
                    "prompt": prompt,
                    "task_type": "simple",  # phi3 handles this
                },
            )
            r.raise_for_status()
            analysis = r.json().get("response_text", "")
    except Exception as e:
        analysis = f"Analysis unavailable: {e}"

    return {
        "fit_score": score,
        "matched_keywords": sorted(matched),
        "missing_keywords": sorted(missing)[:15],  # top 15 missing
        "analysis": analysis,
        "total_jd_keywords": len(jd_keywords),
        "total_matched": len(matched),
    }
