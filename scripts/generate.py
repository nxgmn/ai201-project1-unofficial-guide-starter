#!/usr/bin/env python3
"""Generation module: retrieves context, calls Groq LLM, returns grounded answer.

Pipeline stage: Retrieval → Generation
  - Retrieves top-k chunks via retrieve()
  - Formats them as numbered source blocks in the user message
  - Prompts llama-3.3-70b-versatile to answer ONLY from those chunks
  - Programmatically guarantees source attribution in the returned dict

Usage:
  python scripts/generate.py
  python scripts/generate.py --query "Which CS cluster is best for AI jobs?"
"""

from __future__ import annotations

import argparse
import os
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Resolve project root regardless of where this script is called from.
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Import retrieve from the same scripts/ package.
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from retrieve import retrieve

MODEL = "llama-3.3-70b-versatile"
DEFAULT_K = 5

SYSTEM_PROMPT = """\
You are an assistant for RIT CS students. Your job is to answer questions \
using ONLY the source excerpts provided in each message. \
Do not draw on any knowledge outside those excerpts — not your training data, \
not general knowledge about universities, not anything else.

Rules:
1. Answer directly and specifically from the excerpts.
2. Cite the source document by filename for every claim \
   (e.g. "according to 06_reddit_cs_coops.txt, ...").
3. If the excerpts do not contain enough information to answer the question, \
   respond with exactly: \
   "I don't have enough information on that topic in my sources."
4. Do not speculate, generalize, infer, or add anything not stated in the excerpts.\
"""


def _format_context(chunks: list[dict]) -> str:
    blocks: list[str] = []
    for i, c in enumerate(chunks, 1):
        source = Path(c["source_file"]).name
        blocks.append(
            f"[{i}] {source} (chunk {c['chunk_index']})\n"
            f"---\n{c['text']}\n---"
        )
    return "\n\n".join(blocks)


def ask(question: str, k: int = DEFAULT_K) -> dict:
    """Retrieve context and generate a grounded answer.

    Returns:
      answer  – LLM response, grounded in retrieved chunks only
      sources – deduplicated list of source filenames used as context
      chunks  – full retrieved chunk dicts (for debugging / UI)
    """
    chunks = retrieve(question, k=k)
    context = _format_context(chunks)

    user_message = (
        f"Source excerpts:\n\n{context}\n\n"
        f"Question: {question}"
    )

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,          # deterministic — minimises hallucination
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
    )

    answer = response.choices[0].message.content.strip()

    # Programmatically build the source list regardless of what the LLM cited.
    seen: set[str] = set()
    sources: list[str] = []
    for c in chunks:
        name = Path(c["source_file"]).name
        if name not in seen:
            seen.add(name)
            sources.append(f"{name}  (distance: {c['distance']:.4f})")

    return {"answer": answer, "sources": sources, "chunks": chunks}


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What guidance appears in the sources about preparing for CS co-ops?",
    "What do students say about choosing CS cluster electives at RIT?",
    "What is the food like in the RIT dining halls?",   # out-of-scope — should decline
]


def _print_result(question: str, result: dict) -> None:
    width = 72
    print(f"\n{'=' * width}")
    print(f"Q: {question}")
    print(f"{'=' * width}")
    print()
    for line in result["answer"].splitlines():
        print(textwrap.fill(line, width=width) if line.strip() else "")
    print()
    print("Retrieved from:")
    for s in result["sources"]:
        print(f"  • {s}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the RIT CS unofficial guide")
    parser.add_argument("--query", default=None)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    args = parser.parse_args()

    queries = [args.query] if args.query else TEST_QUERIES
    for q in queries:
        result = ask(q, k=args.k)
        _print_result(q, result)


if __name__ == "__main__":
    main()
