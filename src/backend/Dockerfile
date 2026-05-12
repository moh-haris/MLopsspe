# Using a minimal Python image to save RAM
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for SQLite and building specific python packages
RUN apt-get update && apt-get install -y sqlite3 build-essential && rm -rf /var/lib/apt/lists/*

# THE 8GB SURVIVAL HACK: Install the CPU-only version of PyTorch. 
# This prevents downloading 2GB+ of unused NVIDIA CUDA binaries.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the ML, API dependencies, hvac for Vault,
# AND python-json-logger for structured ELK-compatible JSON logging
RUN pip install fastapi uvicorn gliner sentence-transformers chromadb groq hvac python-json-logger

# Copy your backend code into the container
# NOTE: Build context is now the project root, so paths are relative to that
COPY src/backend/ /app/

# Bake the dataset into a SAFE location that won't be shadowed by the PVC mount
# /app/seed-data/ is NOT mounted, so this file persists inside the image
COPY data/telecom_sops_500_stress_test.json /app/seed-data/telecom_sops_500_stress_test.json

# PRE-DOWNLOAD MODELS: Bake the models directly into the Docker image during the build.
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_medium-v2.1')"
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5'); SentenceTransformer('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose the FastAPI port
EXPOSE 8000

# Use entrypoint script: seeds data → runs ingestion → starts uvicorn
ENTRYPOINT ["/app/entrypoint.sh"]