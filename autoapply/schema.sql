-- Schema for tracking job applications and AI-generated assets
-- Resume storage (chunked for RAG)
CREATE TABLE IF NOT EXISTS resume_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section     TEXT,        -- 'experience', 'skills', 'projects', 'education'
    content     TEXT,        -- the actual bullet or section text
    embedding   TEXT,        -- stored in ChromaDB, this is just the ref
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Job applications tracker
CREATE TABLE IF NOT EXISTS applications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company          TEXT NOT NULL,
    role             TEXT NOT NULL,
    jd_text          TEXT NOT NULL,
    fit_score        INTEGER,
    missing_keywords TEXT[],
    matched_keywords TEXT[],
    tailored_bullets JSONB,
    cover_letter     TEXT,
    status           TEXT DEFAULT 'applied',
    applied_at       TIMESTAMPTZ DEFAULT NOW(),
    response_at      TIMESTAMPTZ,
    notes            TEXT
);

-- Keyword performance tracker (feedback loop)
CREATE TABLE IF NOT EXISTS keyword_outcomes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword     TEXT NOT NULL,
    used_in     UUID REFERENCES applications(id),
    got_response BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);