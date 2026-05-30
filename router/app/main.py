"""
Layer 2: Smart Router
- Classifies incoming prompts by task type
- Selects the best model using routing weights from PostgreSQL
- Calls the chosen LLM backend (Ollama or Gemini)
- Stores the result for the feedback engine to score
"""

import os
import time
import uuid
import logging
import httpx
import asyncpg
import chromadb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from contextlib import asynccontextmanager
from classifier import TaskClassifier
from selector import ModelSelector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App lifecycle ────────────────────────────────────────────────────────────

db_pool = None
chroma_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, chroma_client
    db_pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=2, max_size=10
    )

    # ChromaDB v0.6.x — parse host and port from URL
    chroma_url = os.environ.get("CHROMA_URL", "http://chromadb:8000")
    chroma_host = chroma_url.replace("http://", "").split(":")[0]
    chroma_port = (
        int(chroma_url.replace("http://", "").split(":")[1])
        if ":" in chroma_url.replace("http://", "")
        else 8000
    )
    chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

    yield
    await db_pool.close()


app = FastAPI(title="AI Smart Router", lifespan=lifespan)

# ─── Models ───────────────────────────────────────────────────────────────────


class RouteRequest(BaseModel):
    prompt: str
    task_type: str = "auto"
    request_id: str | None = None


class RouteResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    response_text: str
    model_used: str
    task_type: str
    latency_ms: int
    request_id: str
    cache_hit: bool = False


# ─── Core routing logic ───────────────────────────────────────────────────────

classifier = TaskClassifier()
selector = ModelSelector()


@app.post("/route", response_model=RouteResponse)
async def route(req: RouteRequest):
    request_id = req.request_id or str(uuid.uuid4())
    start = time.time()

    # Step 1: Classify the task
    task_type = (
        req.task_type if req.task_type != "auto" else classifier.classify(req.prompt)
    )

    # Step 2: Check semantic cache in ChromaDB
    cached = await check_semantic_cache(req.prompt)
    if cached:
        latency_ms = int((time.time() - start) * 1000)
        await log_response(
            request_id,
            req.prompt,
            cached["task_type"],
            cached["model_used"],
            cached["response_text"],
            latency_ms,
        )
        return RouteResponse(
            response_text=cached["response_text"],
            model_used=cached["model_used"],
            task_type=cached["task_type"],
            latency_ms=latency_ms,
            request_id=request_id,
            cache_hit=True,
        )

    # Step 3: Select model using routing weights from PostgreSQL
    async with db_pool.acquire() as conn:
        weights = await conn.fetch(
            "SELECT model_name, weight FROM routing_weights WHERE task_type=$1 ORDER BY weight DESC",
            task_type,
        )
    model_name = selector.select(weights)

    # Step 4: Call the LLM backend (with automatic fallback)
    try:
        response_text = await call_llm(model_name, req.prompt)
    except (httpx.TimeoutException, Exception) as e:
        # If the primary model fails and it wasn't already the fallback, try the fallback model
        if model_name != selector.FALLBACK_MODEL:
            logger.warning(
                f"Primary model {model_name} failed ({type(e).__name__}). Retrying with fallback: {selector.FALLBACK_MODEL}"
            )
            try:
                model_name = selector.FALLBACK_MODEL
                response_text = await call_llm(model_name, req.prompt)
            except Exception as final_e:
                logger.error(f"Fallback model also failed: {final_e}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Both primary ({model_name}) and fallback models failed.",
                )
        else:
            # If the fallback itself failed or timed out
            error_type = "Timeout" if isinstance(e, httpx.TimeoutException) else "Error"
            logger.error(f"{error_type} on fallback model {model_name}: {e}")
            raise HTTPException(
                status_code=504 if error_type == "Timeout" else 502, detail=str(e)
            )

    latency_ms = int((time.time() - start) * 1000)

    # Step 5: Store in semantic cache + log for feedback engine
    await store_in_cache(req.prompt, response_text, model_name)
    await log_response(
        request_id, req.prompt, task_type, model_name, response_text, latency_ms
    )

    return RouteResponse(
        response_text=response_text,
        model_used=model_name,
        task_type=task_type,
        latency_ms=latency_ms,
        request_id=request_id,
    )


# ─── LLM backend callers ──────────────────────────────────────────────────────


async def call_llm(model_name: str, prompt: str) -> str:
    if model_name.startswith("ollama/"):
        return await call_ollama(model_name.split("/")[1], prompt)
    elif model_name.startswith("gemini/"):
        return await call_gemini(prompt)
    raise HTTPException(
        status_code=500, detail=f"Unknown backend for model: {model_name}"
    )


async def call_ollama(model: str, prompt: str) -> str:
    url = f"{os.environ.get('OLLAMA_URL', 'http://ollama:11434')}/api/generate"
    # Increased timeout to 300s to allow for local model cold-starts or slow generation
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            url, json={"model": model, "prompt": prompt, "stream": False}
        )
        r.raise_for_status()
        return r.json()["response"]


async def call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    # Increased timeout to 120s for large prompt processing
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=body)
        if r.status_code != 200:
            error_msg = r.json().get("error", {}).get("message", "Unknown Gemini Error")
            raise RuntimeError(f"Gemini API error: {error_msg}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


# ─── Semantic cache ───────────────────────────────────────────────────────────

CACHE_COLLECTION = "prompt_cache"
SIMILARITY_THRESHOLD = 0.50


async def check_semantic_cache(prompt: str) -> dict | None:
    try:
        col = chroma_client.get_or_create_collection(CACHE_COLLECTION)
        results = col.query(query_texts=[prompt], n_results=1)
        if results["distances"] and results["distances"][0]:
            distance = results["distances"][0][0]
            similarity = 1 - distance
            if similarity >= SIMILARITY_THRESHOLD:
                meta = results["metadatas"][0][0]
                return {
                    "response_text": meta["response_text"],
                    "model_used": meta["model_name"],
                    "task_type": meta["task_type"],
                }
    except Exception as e:
        logger.error(f"Semantic cache lookup failed: {e}")
    return None


async def store_in_cache(prompt: str, response: str, model: str):
    try:
        col = chroma_client.get_or_create_collection(CACHE_COLLECTION)
        col.add(
            documents=[prompt],
            metadatas=[
                {"response_text": response, "model_name": model, "task_type": "cached"}
            ],
            ids=[str(uuid.uuid4())],
        )
    except Exception as e:
        logger.error(f"Failed to store in semantic cache: {e}")


# ─── Logging ──────────────────────────────────────────────────────────────────


async def log_response(request_id, prompt, task_type, model, response, latency_ms):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO request_log (request_id, prompt, task_type, model_used, response_text, latency_ms)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            request_id,
            prompt,
            task_type,
            model,
            response,
            latency_ms,
        )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """
    Dummy metrics endpoint to satisfy monitoring scrapes and reduce 404 log noise.
    """
    return {
        "message": "Metrics collection not implemented in Router. See Feedback service."
    }
