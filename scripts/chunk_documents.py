#!/usr/bin/env python3
"""Load text documents, clean content, and generate token-overlap chunks.

Defaults match planning.md:
- chunk size: 400 tokens
- overlap: 70 tokens

Usage:
  python scripts/chunk_documents.py
  python scripts/chunk_documents.py --chunk-size 400 --overlap 70
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = ROOT / "documents"
OUTPUT_JSONL = DOCUMENTS_DIR / "chunks.jsonl"
OUTPUT_SUMMARY = DOCUMENTS_DIR / "chunk_summary.json"

DEFAULT_CHUNK_SIZE = 400
DEFAULT_OVERLAP = 70


def clean_text(text: str) -> str:
    """Normalize whitespace and strip scraping noise that survives into document files."""
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip RateMyProfessors footer boilerplate that appears at the end of every page.
    text = re.sub(
        r"Help\s+Site Guidelines\s+Terms\s*&\s*Conditions\s+Privacy Policy.*?All Rights Reserved",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Strip residual inline link markup and navigation fragments.
    text = re.sub(r"\[(.*?)\]\((https?://[^)]+)\)", r"\1", text)
    text = re.sub(r"Professors\s+cancel\s+at\s+Log\s+In\s+Sign\s+Up\s+Help", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bJump\s+To\s+Ratings\b", "", text, flags=re.IGNORECASE)

    # Collapse internal whitespace while preserving paragraph breaks.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    """Simple whitespace tokenizer for reproducible chunk boundaries."""
    return [tok for tok in text.split() if not re.fullmatch(r"[_\-]+", tok)]


def is_non_substantive_document(text: str) -> bool:
    """Filter out scrape failures and placeholder content."""
    lowered = text.lower()
    bad_markers = [
        "failed to scrape",
        "reddit json failed",
        "mirror returned blocked-page content",
        "this page appears to require javascript",
    ]
    return any(marker in lowered for marker in bad_markers)


def chunk_tokens(tokens: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not tokens:
        return []

    step = chunk_size - overlap
    chunks: list[list[str]] = []
    for start in range(0, len(tokens), step):
        end = start + chunk_size
        chunk = tokens[start:end]
        if not chunk:
            continue
        chunks.append(chunk)
        if end >= len(tokens):
            break
    return chunks


def iter_source_files(documents_dir: Path) -> list[Path]:
    """Return source text documents to chunk.

    Excludes generated outputs and metadata files.
    """
    excluded = {"scrape_report.json", "chunks.jsonl", "chunk_summary.json", ".gitkeep"}
    files = []
    for path in sorted(documents_dir.glob("*.txt")):
        if path.name in excluded:
            continue
        files.append(path)
    return files


def run(chunk_size: int, overlap: int) -> None:
    source_files = iter_source_files(DOCUMENTS_DIR)
    if not source_files:
        raise FileNotFoundError("No source .txt files found in documents/")

    all_chunk_records: list[dict] = []
    per_file_summary: list[dict] = []
    skipped_files: list[dict] = []

    for file_path in source_files:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_text(raw)
        if is_non_substantive_document(cleaned):
            skipped_files.append(
                {
                    "source_file": str(file_path.relative_to(ROOT)),
                    "reason": "non-substantive scrape error or placeholder content",
                }
            )
            continue

        tokens = tokenize(cleaned)
        token_chunks = chunk_tokens(tokens, chunk_size=chunk_size, overlap=overlap)

        for idx, tok_chunk in enumerate(token_chunks):
            all_chunk_records.append(
                {
                    "chunk_id": f"{file_path.stem}_chunk_{idx:04d}",
                    "source_file": str(file_path.relative_to(ROOT)),
                    "chunk_index": idx,
                    "token_count": len(tok_chunk),
                    "text": " ".join(tok_chunk),
                }
            )

        per_file_summary.append(
            {
                "source_file": str(file_path.relative_to(ROOT)),
                "original_char_count": len(raw),
                "cleaned_char_count": len(cleaned),
                "token_count": len(tokens),
                "chunk_count": len(token_chunks),
            }
        )

    with OUTPUT_JSONL.open("w", encoding="utf-8") as f:
        for record in all_chunk_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "source_document_count": len(source_files),
        "processed_document_count": len(per_file_summary),
        "skipped_document_count": len(skipped_files),
        "skipped_files": skipped_files,
        "total_chunks": len(all_chunk_records),
        "files": per_file_summary,
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Found {len(source_files)} source documents: {len(per_file_summary)} processed, {len(skipped_files)} skipped")
    print(f"Total chunks: {len(all_chunk_records)}")
    print(f"Chunks file: {OUTPUT_JSONL.relative_to(ROOT)}")
    print(f"Summary file: {OUTPUT_SUMMARY.relative_to(ROOT)}")

    print("\n--- 5 Random Chunk Preview ---")
    preview_count = min(5, len(all_chunk_records))
    if preview_count > 0:
        selected = random.sample(all_chunk_records, k=preview_count)
        for item in selected:
            snippet_words = item["text"].split()[:85]
            snippet = " ".join(snippet_words)
            print(
                f"- {item['chunk_id']} | source={item['source_file']} "
                f"| tokens={item['token_count']}\n  {snippet}"
            )
    else:
        print("No chunks generated.")

    if skipped_files:
        print("\n--- Skipped Documents ---")
        for skipped in skipped_files:
            print(f"- {skipped['source_file']}: {skipped['reason']}")

    if len(all_chunk_records) < 50:
        print("\n[Warning] Fewer than 50 chunks across 10 sources; consider smaller chunk size or adding sources.")
    elif len(all_chunk_records) > 2000:
        print("\n[Warning] More than 2000 chunks; consider larger chunk size or reduced overlap.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk documents from documents/*.txt")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(chunk_size=args.chunk_size, overlap=args.overlap)