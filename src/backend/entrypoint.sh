#!/bin/bash
set -e

echo "========================================="
echo "  SecureNOC Backend — Entrypoint"
echo "========================================="

# Step 1: Copy seed dataset into PVC mount if not already present
if [ ! -f /app/data/telecom_sops_500_stress_test.json ]; then
    echo "📂 Seeding dataset from baked image into PVC volume..."
    mkdir -p /app/data/
    cp /app/seed-data/telecom_sops_500_stress_test.json /app/data/
    echo "✅ Dataset seeded successfully."
else
    echo "✅ Dataset already exists in PVC — skipping seed."
fi

# Step 2: Run data ingestion if ChromaDB collection doesn't exist yet
if [ ! -d /app/data/chroma_db ]; then
    echo "🔄 Running data ingestion (SQLite + ChromaDB)..."
    python ingest.py
    echo "✅ Ingestion complete."
else
    echo "✅ ChromaDB already exists — skipping ingestion."
fi

echo "🚀 Starting FastAPI server..."

# Step 3: Start the API (exec replaces shell so signals propagate correctly)
exec uvicorn main:app --host 0.0.0.0 --port 8000 --log-config /app/uvicorn_log_config.json
