#!/usr/bin/env python3
"""Gradio web interface for the RIT CS unofficial guide RAG system.

Usage:
  python app.py
  Then open http://localhost:7860
"""

from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate import ask


def handle_query(question: str) -> tuple[str, str]:
    question = question.strip()
    if not question:
        return "", ""

    result = ask(question)
    sources_text = "\n".join(f"• {s}" for s in result["sources"])
    return result["answer"], sources_text


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

EXAMPLES = [
    "What do students say about preparing for CS co-ops at RIT?",
    "How should I balance my second-year CS course load?",
    "Which CS cluster electives are most popular and why?",
    "What do student reviews say about Professor Phil White?",
    "What are the prerequisites for CSCI 261 Analysis of Algorithms?",
]

with gr.Blocks(title="RIT CS Unofficial Guide") as demo:
    gr.Markdown(
        """
        # RIT CS Unofficial Guide
        Ask questions about RIT's CS courses, curriculum, professors, co-ops, and electives.
        Answers are grounded in student discussions and official RIT documents — not general AI knowledge.
        """
    )

    with gr.Row():
        with gr.Column(scale=3):
            question = gr.Textbox(
                label="Your question",
                placeholder="e.g. Which CS cluster electives are best for AI jobs?",
                lines=2,
            )
        with gr.Column(scale=1, min_width=120):
            btn = gr.Button("Ask", variant="primary", size="lg")

    with gr.Row():
        answer = gr.Textbox(label="Answer", lines=12, interactive=False)

    with gr.Row():
        sources = gr.Textbox(
            label="Retrieved from (sources used as context)",
            lines=5,
            interactive=False,
        )

    gr.Examples(
        examples=EXAMPLES,
        inputs=question,
        label="Example questions",
    )

    btn.click(handle_query, inputs=question, outputs=[answer, sources])
    question.submit(handle_query, inputs=question, outputs=[answer, sources])

if __name__ == "__main__":
    demo.launch()
