-- Gateway audit log: every request/response pair
CREATE TABLE IF NOT EXISTS request_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id    TEXT,
    prompt        TEXT NOT NULL,
    task_type     TEXT,                  -- 'simple', 'code', 'reasoning', 'auto'
    model_used    TEXT,                  -- e.g. 'ollama/phi3', 'gemini/flash'
    response_text TEXT,
    latency_ms    INTEGER,
    api_key_hash  TEXT,                  -- SHA-256 of the key, never store raw
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Per-model routing weights (updated nightly by feedback engine)
CREATE TABLE IF NOT EXISTS routing_weights (
    id           SERIAL PRIMARY KEY,
    task_type    TEXT NOT NULL,          -- e.g. 'simple', 'code', 'reasoning'
    model_name   TEXT NOT NULL,          -- e.g. 'ollama/phi3'
    weight       FLOAT NOT NULL DEFAULT 1.0,
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (task_type, model_name)
);

-- Seed initial routing weights
INSERT INTO routing_weights (task_type, model_name, weight) VALUES
    ('simple',    'ollama/phi3',      1.0),
    ('simple',    'gemini/flash',     0.5),
    ('code',      'ollama/mistral',   1.0),
    ('code',      'ollama/llama3',    0.8),
    ('reasoning', 'ollama/llama3',    1.0),
    ('reasoning', 'gemini/flash',     0.9)
ON CONFLICT DO NOTHING;

-- Response quality scores (written by feedback engine)
CREATE TABLE IF NOT EXISTS response_scores (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id   TEXT NOT NULL,
    model_name   TEXT NOT NULL,
    latency_ms   INTEGER,
    quality_score FLOAT,                 -- heuristic: 0.0–1.0
    scored_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_log_created   ON request_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_model          ON response_scores (model_name);
CREATE INDEX IF NOT EXISTS idx_weights_task          ON routing_weights (task_type);
