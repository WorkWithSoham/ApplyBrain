#!/bin/bash
set -e

echo "──────────────────────────────────────────"
echo "  Smart AI Router — Dev Container Ready"
echo "──────────────────────────────────────────"

# Install Python dependencies from mounted workspace
echo "⏳ Installing Python dependencies..."
pip install --break-system-packages --quiet -r /workspace/router/requirements.txt
pip install --break-system-packages --quiet -r /workspace/feedback/requirements.txt
pip install --break-system-packages --quiet streamlit pandas plotly psycopg2-binary
pip install --break-system-packages --quiet streamlit pandas plotly psycopg2-binary sqlalchemy
echo "✅ Python dependencies installed"

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h postgres -U ai_router -q; do sleep 1; done
echo "✅ PostgreSQL is ready"

# Wait for Ollama
echo "⏳ Waiting for Ollama..."
until curl -s http://ollama:11434/api/tags > /dev/null 2>&1; do sleep 2; done
echo "✅ Ollama is ready"

# Pull models if not already present
MODELS=$(curl -s http://ollama:11434/api/tags | python3 -c \
  "import sys,json; data=json.load(sys.stdin); print(' '.join([m['name'] for m in data.get('models',[])]))" 2>/dev/null || echo "")

for MODEL in "phi3" "mistral" "llama3"; do
  if echo "$MODELS" | grep -q "$MODEL"; then
    echo "✅ Model $MODEL already pulled"
  else
    echo "⬇️  Pulling $MODEL (this may take a few minutes)..."
    curl -s -X POST http://ollama:11434/api/pull \
      -H "Content-Type: application/json" \
      -d "{\"name\": \"$MODEL\", \"stream\": false}" > /dev/null
    echo "✅ $MODEL pulled"
  fi
done

echo ""
echo "🚀 All services ready:"
echo "   Gateway:    http://localhost:8080"
echo "   Router:     http://localhost:8081/docs"
echo "   Feedback:   http://localhost:8082/docs"
echo "   Grafana:    http://localhost:3000  (admin/admin)"
echo "   Prometheus: http://localhost:9090"
echo "   Dashboard:  http://localhost:8501"
echo ""
echo "📝 Quick test:"
echo "   curl -X POST http://localhost:8081/route \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"prompt\": \"What is 2+2?\", \"task_type\": \"auto\"}'"