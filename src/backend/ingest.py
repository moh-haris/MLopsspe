"""
Data Ingestion Script — loads telecom SOPs into SQLite + ChromaDB.

Uses the centralized structured JSON logger so all output is
Kibana-compatible, matching the rest of the backend.
"""

import json
import sqlite3
import os

import chromadb
from sentence_transformers import SentenceTransformer

# --- Structured JSON Logger (centralized) ---
from logger import get_logger

logger = get_logger(__name__)

# Ensure we are using the mounted data volume
DATA_DIR = "/app/data"
JSON_PATH = os.path.join(DATA_DIR, "telecom_sops_500_stress_test.json")
SQLITE_PATH = os.path.join(DATA_DIR, "telecom_sops.db")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma_db")


def ingest_data():
    logger.info("Loading JSON data", extra={"source_file": JSON_PATH})
    with open(JSON_PATH, "r") as f:
        sops = json.load(f)
    logger.info("JSON data loaded", extra={"record_count": len(sops)})

    logger.info("Initializing SQLite", extra={"db_path": SQLITE_PATH})
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS sops (id TEXT, content TEXT)""")

    logger.info("Initializing ChromaDB and BGE model", extra={"chroma_path": CHROMA_PATH})
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(name="sops")
    embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")

    logger.info(
        "Starting SOP embedding (CPU mode — this will take a moment)",
        extra={"total_sops": len(sops)},
    )

    for idx, sop in enumerate(sops, start=1):
        sop_id = sop["sop_id"]
        content = sop["search_content"]

        # 1. Save to SQLite
        cursor.execute("INSERT OR REPLACE INTO sops VALUES (?, ?)", (sop_id, json.dumps(sop)))

        # 2. Save to ChromaDB
        embedding = embedder.encode(content).tolist()
        collection.add(
            ids=[sop_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"vendor": sop.get("vendor", "Unknown")}],
        )

        # Log progress every 50 records to avoid log spam
        if idx % 50 == 0 or idx == len(sops):
            logger.info("Embedding progress", extra={"processed": idx, "total": len(sops)})

    conn.commit()
    conn.close()
    logger.info(
        "Ingestion complete — databases generated",
        extra={"sqlite_path": SQLITE_PATH, "chroma_path": CHROMA_PATH},
    )


if __name__ == "__main__":
    ingest_data()