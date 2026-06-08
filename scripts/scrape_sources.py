#!/usr/bin/env python3
"""Scrape project planning sources into individual documents.

Usage:
  python scripts/scrape_sources.py

Outputs:
  - One text file per source under documents/
  - A scrape report at documents/scrape_report.json
"""

from __future__ import annotations

import json
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - runtime dependency guard
    BeautifulSoup = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "documents"
RAW_DIR = OUTPUT_DIR / "raw"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Source:
    idx: int
    name: str
    url: str
    kind: str


SOURCES: list[Source] = [
    Source(
        1,
        "rit_cs_electives_clusters_pdf",
        "https://www.cs.rit.edu/csdocs/Website/ComputerScienceElectivesandClusters.pdf",
        "pdf",
    ),
    Source(
        2,
        "reddit_cs_core_class_advice",
        "https://www.reddit.com/r/rit/comments/122i0uw/need_advice_on_cs_core_classes/",
        "reddit",
    ),
    Source(
        3,
        "rit_cs_undergrad_flowchart_pdf",
        "https://www.cs.rit.edu/csdocs/Website/CSUndergradFlowChart.pdf",
        "pdf",
    ),
    Source(
        4,
        "reddit_cs_minor_electives",
        "https://www.reddit.com/r/rit/comments/1b36mrf/cs_minor_which_electives_to_take/",
        "reddit",
    ),
    Source(
        5,
        "reddit_second_year_course_flow",
        "https://www.reddit.com/r/rit/comments/1g605qm/second_year_cs_courseflow_is_it_too_much/",
        "reddit",
    ),
    Source(
        6,
        "reddit_cs_coops",
        "https://www.reddit.com/r/rit/comments/m7h2zu/computer_science_bs_coops/",
        "reddit",
    ),
    Source(
        7,
        "reddit_best_cs_cluster_electives",
        "https://www.reddit.com/r/rit/comments/1c4b56w/best_cs_cluster_electives/",
        "reddit",
    ),
    Source(
        8,
        "ratemyprofessors_251460",
        "https://www.ratemyprofessors.com/professor/251460",
        "html",
    ),
    Source(
        9,
        "ratemyprofessors_2638596",
        "https://www.ratemyprofessors.com/professor/2638596",
        "html",
    ),
    Source(
        10,
        "ratemyprofessors_2954361",
        "https://www.ratemyprofessors.com/professor/2954361",
        "html",
    ),
]


def clean_document_text(text: str) -> str:
    """Normalize whitespace and strip common scraping boilerplate."""
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    boilerplate_patterns = [
        r"^\s*Warning:\s*Target URL returned error\s+\d+.*$",
        r"^\s*You've been blocked by network security\.?\s*$",
        r"^\s*To continue, log in to your Reddit account.*$",
        r"^\s*If you think you've been blocked by mistake.*$",
        r"^\s*Markdown Content:\s*$",
        r"^\s*URL Source:\s*https?://\S+\s*$",
        r"^\s*Read more\s*$",
        r"^\s*Share\s*$",
        r"^\s*Cookie[s]?\s*$",
        r"^\s*Accept All\s*$",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    text = re.sub(r"\[(.*?)\]\((https?://[^)]+)\)", r"\1", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch(url: str, timeout: int = 25) -> requests.Response:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def extract_pdf_text(data: bytes) -> str:
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except Exception:
        return (
            "PDF downloaded, but pdfplumber is not installed.\n"
            "Run: pip install pdfplumber\n"
        )

    from io import BytesIO

    text_chunks: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                text_chunks.append(f"# Page {page_num}\n{page_text}")

    return "\n\n".join(text_chunks).strip()


def reddit_json_url(url: str) -> str:
    return url.rstrip("/") + ".json?limit=500"


def jina_mirror_url(url: str) -> str:
    stripped = re.sub(r"^https?://", "", url)
    return f"https://r.jina.ai/http://{stripped}"


def parse_reddit_json(payload: Any) -> str:
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("Unexpected Reddit JSON format")

    post_listing = payload[0]["data"]["children"]
    comments_listing = payload[1]["data"]["children"]

    if not post_listing:
        raise ValueError("No Reddit post found")

    post_data = post_listing[0]["data"]
    lines: list[str] = []
    lines.append(f"Title: {post_data.get('title', '')}")
    lines.append(f"Subreddit: {post_data.get('subreddit', '')}")
    lines.append(f"Author: {post_data.get('author', '')}")
    lines.append(f"Score: {post_data.get('score', '')}")
    lines.append("")
    lines.append("Post body:")
    lines.append(post_data.get("selftext", "").strip())
    lines.append("")
    lines.append("Top-level comments:")

    for item in comments_listing:
        if item.get("kind") != "t1":
            continue
        c = item.get("data", {})
        body = (c.get("body") or "").strip()
        if not body:
            continue
        author = c.get("author", "[deleted]")
        score = c.get("score", "")
        lines.append(f"- {author} (score={score}): {body}")

    return "\n".join(lines).strip()


def extract_reddit_text(url: str) -> str:
    errors: list[str] = []

    try:
        response = fetch(reddit_json_url(url))
        payload = response.json()
        return parse_reddit_json(payload)
    except Exception as exc:  # pylint: disable=broad-except
        errors.append(f"Reddit JSON failed: {exc}")

    try:
        # This mirror often works when Reddit blocks direct scraping requests.
        mirrored = fetch(jina_mirror_url(url), timeout=35)
        text = clean_document_text(mirrored.text)
        if "blocked by network security" in text.lower():
            raise RuntimeError("Mirror returned blocked-page content")
        if text and len(text) > 150:
            return text
        errors.append("Jina mirror returned too little text")
    except Exception as exc:  # pylint: disable=broad-except
        errors.append(f"Jina mirror failed: {exc}")

    raise RuntimeError(" | ".join(errors))


def extract_html_text(url: str) -> str:
    response = fetch(url)
    html = response.text

    if BeautifulSoup is None:
        # Fallback if bs4 isn't available: naive tag stripping.
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return clean_whitespace(text)

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.strip()

    if not text or len(text) < 120:
        # Fallback for highly JS-rendered pages.
        text = (
            "This page appears to require JavaScript for full content.\n"
            "Consider Playwright/Selenium for dynamic scraping.\n\n"
            f"URL: {url}"
        )

    return text


def write_output(source: Source, content: str, suffix: str = ".txt") -> Path:
    filename = f"{source.idx:02d}_{source.name}{suffix}"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def write_raw_output(source: Source, content: str) -> Path:
    filename = f"{source.idx:02d}_{source.name}.raw.txt"
    out_path = RAW_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def process_source(source: Source) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": source.idx,
        "name": source.name,
        "url": source.url,
        "kind": source.kind,
    }

    try:
        if source.kind == "reddit":
            raw_text = extract_reddit_text(source.url)
            raw_path = write_raw_output(source, raw_text)
            text = clean_document_text(raw_text)
            out_path = write_output(source, text)
            record["raw_file"] = str(raw_path.relative_to(ROOT))
        elif source.kind == "pdf":
            resp = fetch(source.url)
            pdf_path = write_output(source, "", suffix=".pdf")
            pdf_path.write_bytes(resp.content)

            raw_text = extract_pdf_text(resp.content)
            raw_path = write_raw_output(source, raw_text)
            extracted = clean_document_text(raw_text)
            txt_path = write_output(source, extracted)
            out_path = txt_path
            record["pdf_file"] = str(pdf_path.relative_to(ROOT))
            record["raw_file"] = str(raw_path.relative_to(ROOT))
        else:
            raw_text = extract_html_text(source.url)
            raw_path = write_raw_output(source, raw_text)
            text = clean_document_text(raw_text)
            out_path = write_output(source, text)
            record["raw_file"] = str(raw_path.relative_to(ROOT))

        record["status"] = "ok"
        record["output_file"] = str(out_path.relative_to(ROOT))
    except Exception as exc:  # pylint: disable=broad-except
        err_text = f"Failed to scrape {source.url}\nError: {exc}\n"
        fallback_path = write_output(source, err_text)
        record["status"] = "error"
        record["error"] = str(exc)
        record["output_file"] = str(fallback_path.relative_to(ROOT))

    return record


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, Any]] = []

    for source in SOURCES:
        print(f"Processing {source.idx:02d}: {source.url}")
        report.append(process_source(source))

    report_path = OUTPUT_DIR / "scrape_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    ok_count = sum(1 for r in report if r.get("status") == "ok")
    err_count = len(report) - ok_count
    print(f"Done. Success: {ok_count}, Errors: {err_count}")
    print(f"Report: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())