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
COPY . /app/

# PRE-DOWNLOAD MODELS: Bake the models directly into the Docker image during the build.
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_medium-v2.1')"
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5'); SentenceTransformer('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Expose the FastAPI port
EXPOSE 8000

# Start the API with structured JSON log config for Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "/app/uvicorn_log_config.json"]