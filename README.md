# ApplyBrain: AI Job Application Intelligence

An intelligent job application assistant built on a self-learning AI router. 
ApplyBrain parses resumes, analyzes Job Descriptions (JDs), calculates match scores, 
identifies missing keywords, and generates tailored cover letters.

## Architecture

```
Client → [Layer 1: Spring Boot Gateway] → [Layer 2: Python Smart Router] → LLM Backends
                                                          ↑
                                          [Layer 3: Feedback Engine] ←────── LLM Responses
```

## Services

| Service        | Tech                        | Port  | Purpose                              |
|----------------|-----------------------------|-------|--------------------------------------|
| `gateway`      | Java 21 + Spring Boot 3     | 8080  | Auth, rate limiting, request logging |
| `router`       | Python 3.11 + FastAPI       | 8081  | Task classification, model selection |
| `feedback`     | Python 3.11 + APScheduler   | 8082  | Scoring, weight updates              |
| `redis`        | Redis 7                     | 6379  | Rate limiting + response caching     |
| `postgres`     | PostgreSQL 16               | 5432  | Audit logs, routing weights, scores  |
| `chromadb`     | ChromaDB                    | 8000  | Semantic cache (vector similarity)   |
| `prometheus`   | Prometheus                  | 9090  | Metrics scraping                     |
| `grafana`      | Grafana                     | 3000  | Observability dashboard              |
| `ollama`       | Ollama                      | 11434 | Local LLM inference                  |

## Prerequisites

- Docker + Docker Compose
- Java 21 (for local gateway dev)
- Python 3.11+ (for local router/feedback dev)
- Ollama installed locally OR via Docker
- Gemini API key (free tier): https://aistudio.google.com

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/WorkWithSoham/ApplyBrain.git
cd applybrain
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 2. Pull Ollama models
ollama pull llama3          # large tasks
ollama pull phi3            # small/simple tasks
ollama pull mistral         # code tasks

# 3. Start everything
docker compose up -d

# 4. Test a request
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-123" \
  -d '{"prompt": "What is 2+2?", "task_type": "auto"}'
```

## Project Structure

```
smart-ai-router/
├── gateway/          # Spring Boot — Layer 1
├── router/           # Python FastAPI — Layer 2
├── feedback/         # Python + APScheduler — Layer 3
├── infra/            # Prometheus + Grafana config
├── docker/           # Dockerfiles per service
├── docker-compose.yml
└── .env.example
```
