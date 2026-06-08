# The Unofficial Guide — Project 1

---

## Domain

This system covers RIT's CS undergraduate program: course curriculum, cluster electives, co-op preparation, second-year workload, and professor reviews. This information is valuable because it is spread across official PDFs, Rate My Professors, Reddit, and department handbooks, and most of the useful stuff is subjective in a way official sources never capture. The course catalog tells you what CSCI 243 covers but not that taking it with CSCI 262 and MATH 251 in the same semester is a common cause of trouble. This system brings both types of information together into one queryable place.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | RIT CS Electives and Clusters PDF | Official PDF | https://www.cs.rit.edu/csdocs/Website/ComputerScienceElectivesandClusters.pdf |
| 2 | Reddit: Need advice on CS core classes | Student discussion | https://www.reddit.com/r/rit/comments/122i0uw/need_advice_on_cs_core_classes/ |
| 3 | RIT CS Undergrad Flowchart PDF | Official PDF | https://www.cs.rit.edu/csdocs/Website/CSUndergradFlowChart.pdf |
| 4 | Reddit: CS minor — which electives to take? | Student discussion | https://www.reddit.com/r/rit/comments/1b36mrf/cs_minor_which_electives_to_take/ |
| 5 | Reddit: Second-year CS course flow | Student discussion | https://www.reddit.com/r/rit/comments/1g605qm/second_year_cs_courseflow_is_it_too_much/ |
| 6 | Reddit: Computer Science BS co-ops | Student discussion | https://www.reddit.com/r/rit/comments/m7h2zu/computer_science_bs_coops/ |
| 7 | Reddit: Best CS cluster electives | Student discussion | https://www.reddit.com/r/rit/comments/1c4b56w/best_cs_cluster_electives/ |
| 8 | Rate My Professors — Phil White (CSCI 250) | Professor reviews | https://www.ratemyprofessors.com/professor/251460 |
| 9 | Rate My Professors — Tony Audi (CSCI 140/141) | Professor reviews | https://www.ratemyprofessors.com/professor/2638596 |
| 10 | Rate My Professors — Abeer Ahmad (CSCI 243) | Professor reviews | https://www.ratemyprofessors.com/professor/2954361 |

**Note on sources 2, 4-7:** Reddit returned 403 errors on all scraping attempts including the JSON API, old.reddit.com, and the Jina mirror. These files were replaced with manually curated content on the same topics, formatted the same way a successful scrape would have. Source 3 is a visual flowchart PDF that pdfplumber could not extract cleanly even with layout mode, so it was manually transcribed into prose.

---

## Chunking Strategy

**Chunk size:** 400 tokens

**Overlap:** 70 tokens

**Why these choices fit your documents:**
The dataset is mostly short-form, subjective text (Reddit and professor reviews), where smaller chunks preserve tone and specific recommendations. A 70-token overlap keeps adjacent context when advice spans chunk boundaries. This still handles longer PDF passages without creating overly broad chunks that dilute retrieval precision.

Preprocessing included HTML entity decoding, stripping RateMyProfessors footer boilerplate, removing scraper error artifacts, and collapsing whitespace. Single-letter token filtering was removed because it was silently dropping grade letters like "C" from "C or higher."

**Final chunk count:** 24 chunks across 10 documents

---

## Embedding Model

**Model used:** `all-MiniLM-L6-v2` via `sentence-transformers`, running locally with no API key or rate limits. Stored in ChromaDB with cosine distance.

**Production tradeoff reflection:**
For this class project, all-MiniLM-L6-v2 is a good balance of quality, speed, and simplicity. If cost were not a constraint in production, I would test larger embedding models that usually improve semantic accuracy on nuanced opinion text (for example, mixed sentiment in Reddit threads). The tradeoff is higher latency and compute cost. I would also evaluate models with stronger long-context handling for PDF-derived chunks and compare retrieval quality using real user queries. Since the corpus is English-only and domain-specific, multilingual support is less important than precision on terms like course numbers, professor names, workload, and co-op advice.

---

## Grounded Generation

**System prompt grounding instruction:**

The system passes this to `llama-3.3-70b-versatile` via Groq:

> "You are an assistant for RIT CS students. Answer questions using ONLY the source excerpts provided in this message. Do not draw on any knowledge outside those excerpts, not your training data, not general knowledge about universities, not anything else.
>
> Rules:
> 1. Answer directly and specifically from the excerpts.
> 2. Cite the source document by filename for every claim (e.g. "according to 06_reddit_cs_coops.txt, ...").
> 3. If the excerpts do not contain enough information to answer the question, respond with exactly: "I don't have enough information on that topic in my sources."
> 4. Do not speculate, generalize, infer, or add anything not stated in the excerpts."

`temperature=0` is set to keep responses deterministic. Each chunk is passed to the model as a labeled block with its filename so the model has concrete citation anchors.

**How source attribution is surfaced in the response:**

Two ways. The system prompt tells the model to cite filenames inline. The `ask()` function in `scripts/generate.py` also builds a source list programmatically from chunk metadata regardless of what the model cited, so attribution shows up in the UI even if the model's inline citations are off.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What do students say are the biggest factors when choosing CS electives at RIT? | Common factors like workload, professor teaching style, relevance to career goals, and schedule fit | Covered employer recognition, prerequisites, and depth vs. breadth but missed workload and professor style. The most relevant doc (`07`) was not retrieved. | Partially relevant | Partially accurate |
| 2 | How do students describe balancing second-year CS course load at RIT? | Students discuss avoiding overly heavy combinations in one term and planning around difficulty and time demands | Correctly identified 243+262+MATH 251 as a risky combination, described mid-semester drops, recommended staggering. | Relevant | Accurate |
| 3 | What guidance appears in the sources about preparing for CS co-ops? | Building projects, practicing interviews and resumes, planning coursework to be job-ready | GitHub portfolio, LeetCode prep, soft skills, career center resume reviews, CSCI 261 for interviews, CSCI 99 deadlines. Both co-op chunks were in top 2. | Relevant | Accurate |
| 4 | How should a student use official curriculum documents versus student opinion sources? | Official RIT PDFs are authoritative for requirements and prereqs. Reddit and RMP provide subjective experience context. | Got the general framing right but pulled loosely related chunks. All distances above 0.66. Sources cited are real but not actually about this topic. | Off-target | Partially accurate |
| 5 | What kind of professor-related information can be extracted from review sources? | Grading strictness, clarity, workload, class organization. Opinions are subjective. | Listed quality rating, difficulty, would-take-again, teaching style, availability, and noted to take extreme reviews with a grain of salt. | Partially relevant | Accurate |

---

## Failure Case Analysis

**Question that failed:**
"How should a student use official curriculum documents versus student opinion sources?"

**What the system returned:**
All five retrieved chunks had distances above 0.66. The model still produced an answer, citing real sources like `01_rit_cs_electives_clusters_pdf.txt` and `02_reddit_cs_core_class_advice.txt`. But those citations are misleading. The `01` citation just mentions that the CS Handbook exists. The `02` citation is about using syllabi and sample exams to study, not about when to trust official vs. opinion sources. The answer sounds correct but was stitched together from content that does not actually address the question.

**Root cause (tied to a specific pipeline stage):**
This fails at the corpus design stage. The question is meta-level: it asks about the relationship between document types. None of the 10 documents discuss that distinction. They are the official and opinion sources, but none of them say "use the PDF for requirements and Reddit for workload advice." Because the corpus has no text that matches this query, retrieval returned high-distance chunks with no real relevance. The generation stage received five weakly-related context blocks and synthesized a plausible answer from them instead of declining. The distances were not high enough to trigger the system's out-of-scope response the way a completely unrelated question would.

**What you would change to fix it:**
Add a distance threshold to `retrieve()` so that if all top-k distances exceed 0.65, the system declines before calling the LLM. This prevents the model from constructing answers from irrelevant context. The evaluation question itself should also be reworked to be answerable from the corpus, or a short meta-document should be added that explicitly addresses how to use each source type.

---

## Spec Reflection

**One way the spec helped you during implementation:**
The chunking strategy section in planning.md set a clear quality standard: chunks need to preserve tone and specific recommendations from short-form opinion text. When the flowchart PDF extraction produced garbled output, that standard made the decision clear. A garbled chunk fails before retrieval even starts and cannot be fixed by tuning later. The spec gave a concrete bar to evaluate against rather than a vague goal.

**One way your implementation diverged from the spec, and why:**
The planning.md pipeline diagram specifies FAISS as the vector store, but the implementation uses ChromaDB. ChromaDB was already pinned in requirements.txt and installed in the project environment, so switching to it avoided adding a second vector library for the same functionality. ChromaDB also handles persistence and metadata storage without extra serialization steps that FAISS requires. For a 24-chunk corpus the performance difference is irrelevant.

---

## AI Usage

**Instance 1 — Generating the embedding and retrieval scripts**

- *What I gave the AI:* The Retrieval Approach section and pipeline diagram from planning.md, plus the chunk schema from chunks.jsonl.
- *What it produced:* `scripts/embed_chunks.py` and `scripts/retrieve.py` with a working ChromaDB index and retrieval function.
- *What I changed or overrode:* The generated embed script used `get_or_create_collection` which would duplicate chunks on re-runs. I changed it to delete and recreate the collection each time. I also added `hnsw:space=cosine` because the generated code defaulted to L2 distance, which is less appropriate for sentence embeddings.

**Instance 2 — Fixing the 5 failed Reddit source files**

- *What I gave the AI:* The 5 failed source files containing only scrape error messages, the original URLs from planning.md, and the format from a successful scrape as a reference.
- *What it produced:* Five curated documents around 600 words each covering core class advice, CS minor electives, second-year workload, co-op prep, and cluster elective recommendations.
- *What I changed or overrode:* A few facts were wrong for RIT specifically. One draft said CSCI 243 requires only CSCI 141 when the actual prerequisite is CSCI 142 with a C or higher. I corrected these against the official flowchart PDF. I also added a "curated summary" label to each file header so the grounding mechanism would not treat curated content as a primary source.
