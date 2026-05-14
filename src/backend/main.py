import os
import json
import uuid
import time
import sqlite3
import traceback

import chromadb
import hvac
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder
from gliner import GLiNER
from groq import Groq

# --- Structured JSON Logger (centralized) ---
from logger import get_logger, setup_uvicorn_logging

logger = get_logger(__name__)

app = FastAPI()


# ---------------------------------------------------------------------------
# Startup & Shutdown Events — structured logs
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    """Override Uvicorn loggers at startup so ALL output is JSON."""
    setup_uvicorn_logging()
    logger.info("Application startup complete", extra={"event": "startup"})


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Application shutdown initiated", extra={"event": "shutdown"})


# ---------------------------------------------------------------------------
# Request Logging Middleware — replaces the old print(json.dumps(...))
# ---------------------------------------------------------------------------
@app.middleware("http")
async def structured_request_logging_middleware(request: Request, call_next):
    """
    Logs every HTTP request/response as a structured JSON object.
    Generates a unique request_id (UUID4) per request for distributed tracing.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Attach request_id so downstream handlers can access it
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    except Exception:
        # Catch unhandled exceptions so they get logged as JSON, not plaintext
        latency_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            "Unhandled exception during request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "client_ip": request.client.host if request.client else "unknown",
                "latency_ms": latency_ms,
                "exc_info": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
            headers={"X-Request-ID": request_id},
        )

    latency_ms = round((time.time() - start_time) * 1000, 2)
    status_code = response.status_code

    # Choose log level based on status code
    log_extra = {
        "request_id": request_id,
        "method": request.method,
        "path": str(request.url.path),
        "status_code": status_code,
        "latency_ms": latency_ms,
        "client_ip": request.client.host if request.client else "unknown",
    }

    if status_code >= 500:
        logger.error("Request completed", extra=log_extra)
    elif status_code >= 400:
        logger.warning("Request completed", extra=log_extra)
    else:
        logger.info("Request completed", extra=log_extra)

    # Return request_id in response header for client-side tracing
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_DIR = "/app/data"
SQLITE_PATH = os.path.join(DATA_DIR, "telecom_sops.db")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma_db")


# ---------------------------------------------------------------------------
# Vault Integration — structured logging (no secrets logged)
# ---------------------------------------------------------------------------
logger.info("Connecting to HashiCorp Vault", extra={"vault_addr": os.getenv("VAULT_ADDR", "http://vault:8200")})
try:
    vault_client = hvac.Client(
        url=os.getenv("VAULT_ADDR", "http://vault-service:8200"),
        token=os.getenv("VAULT_TOKEN"),
    )
    # Read the secret injected into Vault
    secret_response = vault_client.secrets.kv.v2.read_secret_version(path="llm-credentials")
    GROQ_API_KEY = secret_response["data"]["data"]["groq_key"]
    logger.info("API key retrieved securely from Vault", extra={"secret_path": "llm-credentials"})
except Exception as e:
    logger.critical(
        "Failed to retrieve API key from Vault",
        extra={"error": str(e), "hint": "Did you inject the secret into Vault?"},
    )
    raise SystemExit("FATAL: Cannot start without Groq API key. Check Vault configuration.")


# ---------------------------------------------------------------------------
# CPU-Only Model Initialization — structured logging
# ---------------------------------------------------------------------------
logger.info("Loading ML models into RAM (CPU mode)")

bi_encoder = SentenceTransformer("BAAI/bge-base-en-v1.5", device="cpu")
logger.info("Model loaded", extra={"model": "BAAI/bge-base-en-v1.5", "type": "bi-encoder"})

cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
logger.info("Model loaded", extra={"model": "cross-encoder/ms-marco-MiniLM-L-6-v2", "type": "cross-encoder"})

ner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
logger.info("Model loaded", extra={"model": "urchade/gliner_medium-v2.1", "type": "ner"})

client = Groq(api_key=GROQ_API_KEY)
logger.info("All models and clients initialized successfully")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str


def get_db_connection():
    return sqlite3.connect(SQLITE_PATH)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post("/ask")
async def ask_question(request: QueryRequest, raw_request: Request):
    """RAG pipeline: NER → Vector Search → Rerank → LLM Generation."""
    request_id = getattr(raw_request.state, "request_id", "N/A")

    try:
        # Step A: Entity Extraction (GLiNER)
        entities = ner_model.predict_entities(request.question, labels=["vendor", "device", "protocol"])
        logger.info(
            "Entity extraction complete",
            extra={"request_id": request_id, "entity_count": len(entities)},
        )

        # Step B: Vector Search (ChromaDB)
        chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = chroma_client.get_collection(name="sops")
        query_embedding = bi_encoder.encode(request.question).tolist()

        results = collection.query(query_embeddings=[query_embedding], n_results=5)

        if not results["ids"][0]:
            logger.info("No relevant SOPs found", extra={"request_id": request_id})
            return {"answer": "No relevant SOPs found in the database.", "sources": []}

        doc_ids = results["ids"][0]
        logger.info(
            "Vector search complete",
            extra={"request_id": request_id, "candidates_found": len(doc_ids)},
        )

        # Step C: Reranking (Cross-Encoder)
        conn = get_db_connection()
        cursor = conn.cursor()
        candidates = []
        for doc_id in doc_ids:
            cursor.execute("SELECT content FROM sops WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if row:
                candidates.append(json.loads(row[0]))
        conn.close()

        # For this MVP, take the top 3 from the bi-encoder to save CPU cycles
        top_candidates = candidates[:3]

        # Step D: Final Generation (Groq LLM)
        context = "\n---\n".join([c["search_content"] for c in top_candidates])
        prompt = (
            f"Use the following telecom SOP context to answer the NOC engineer's question: "
            f"{request.question}\n\nContext:\n{context}"
        )

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )

        logger.info(
            "LLM generation complete",
            extra={"request_id": request_id, "model": "llama-3.1-8b-instant"},
        )

        return {"answer": completion.choices[0].message.content, "sources": doc_ids[:3]}

    except Exception as e:
        # Structured exception log — stack trace captured via exc_info=True
        logger.exception(
            "Error processing query",
            extra={
                "request_id": request_id,
                "endpoint": "/ask",
                "question_length": len(request.question),
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "Backend is running"}
