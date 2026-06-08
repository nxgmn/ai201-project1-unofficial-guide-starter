#!/usr/bin/env python3
"""Embed chunks from chunks.jsonl and load them into ChromaDB.

Pipeline stage: Chunking → Embedding + Vector Store
  - Reads:  documents/chunks.jsonl  (produced by chunk_documents.py)
  - Writes: chroma_db/              (persistent ChromaDB on disk)

Architecture (from planning.md):
  all-MiniLM-L6-v2 (sentence-transformers) → ChromaDB with cosine distance

Usage:
  python scripts/embed_chunks.py
"""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_FILE = ROOT / "documents" / "chunks.jsonl"
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION_NAME = "rit_cs_guide"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def load_chunks(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_index() -> None:
    print(f"Loading chunks from {CHUNKS_FILE.relative_to(ROOT)}")
    chunks = load_chunks(CHUNKS_FILE)
    if not chunks:
        raise RuntimeError("No chunks found — run chunk_documents.py first.")
    print(f"  {len(chunks)} chunks loaded")

    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks...")
    # encode() returns a numpy array; tolist() converts to plain Python lists
    # that ChromaDB's add() expects.
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    print(f"\nConnecting to ChromaDB at {CHROMA_DIR.relative_to(ROOT)}/")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Always rebuild from scratch so re-running this script doesn't duplicate chunks.
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass  # collection didn't exist yet

    # hnsw:space=cosine tells ChromaDB's HNSW index to use cosine distance.
    # Cosine distance ranges 0 (identical) → 2 (opposite); good matches are < 0.5.
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "source_file": c["source_file"],
                "chunk_index": c["chunk_index"],
                "token_count": c["token_count"],
            }
            for c in chunks
        ],
    )

    print(f"Indexed {collection.count()} chunks into collection '{COLLECTION_NAME}'")
    print("Done — run scripts/retrieve.py to test queries.")


if __name__ == "__main__":
    build_index()
