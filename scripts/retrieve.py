#!/usr/bin/env python3
"""Retrieval function for the RIT CS unofficial guide RAG pipeline.

Pipeline stage: Vector Store → Retrieval
  - Queries the ChromaDB collection built by embed_chunks.py
  - Returns top-k chunks ranked by cosine distance (lower = more similar)

Usage (standalone test):
  python scripts/retrieve.py
  python scripts/retrieve.py --query "which CS cluster is best for AI jobs?"
  python scripts/retrieve.py --query "..." --k 3

Import in generation stage:
  from scripts.retrieve import retrieve
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION_NAME = "rit_cs_guide"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_K = 5

# Module-level singletons — loaded once, reused across calls.
_model: SentenceTransformer | None = None
_collection: chromadb.Collection | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def retrieve(query: str, k: int = DEFAULT_K) -> list[dict]:
    """Return the top-k most relevant chunks for a query string.

    Each result is a dict with:
      text        – full chunk text
      source_file – original document path (e.g. documents/06_reddit_cs_coops.txt)
      chunk_index – position of this chunk within its source document
      token_count – number of tokens in this chunk
      distance    – cosine distance; 0.0 = identical, lower is better
    """
    model = _get_model()
    collection = _get_collection()

    # collection.query() takes a list of query embeddings (one per query).
    # We always pass a single query, so results are indexed at [0].
    query_embedding = model.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    return [
        {
            "text": doc,
            "source_file": meta["source_file"],
            "chunk_index": meta["chunk_index"],
            "token_count": meta["token_count"],
            "distance": round(dist, 4),
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


# ---------------------------------------------------------------------------
# Test harness — 3 of the 5 evaluation queries from planning.md
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What do students say are the biggest factors when choosing CS electives at RIT?",
    "How do students describe balancing second-year CS course load at RIT?",
    "What guidance appears in the sources about preparing for CS co-ops?",
]


def _print_results(query: str, results: list[dict]) -> None:
    print(f"\n{'=' * 72}")
    print(f"Query: {query}")
    print(f"{'=' * 72}")
    for i, r in enumerate(results, 1):
        source = Path(r["source_file"]).name
        score_label = "✓" if r["distance"] < 0.5 else "!"
        print(f"\n[{i}] {score_label} distance={r['distance']:.4f}  {source}  chunk={r['chunk_index']}")
        print("-" * 72)
        preview = r["text"][:600]
        print(textwrap.fill(preview, width=72))
        if len(r["text"]) > 600:
            print("    [... truncated]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the RIT CS guide vector store")
    parser.add_argument("--query", default=None, help="Single query to run")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Number of results")
    args = parser.parse_args()

    queries = [args.query] if args.query else TEST_QUERIES
    for q in queries:
        results = retrieve(q, k=args.k)
        _print_results(q, results)


if __name__ == "__main__":
    main()
