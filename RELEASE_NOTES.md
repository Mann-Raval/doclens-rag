# DocLens v1.0 — Basic RAG learning demo

Release date: 2026-10-11. App build: 1.3.15 (the deployment build sequence is
retained from testing; v1.0 names the first completed learning milestone).

## Included

- Multi-PDF text ingestion, cleanup, page metadata, chunking and upload validation.
- Local MiniLM embeddings and session-owned, ephemeral Chroma collections.
- Gemini answers, streaming for ordinary Q&A, compact numbered citations and
  inspectable source excerpts.
- Summaries, factual questions, conversational follow-ups, and document comparisons.
- Comparison routing for common equivalent phrasings, chapter pairs and filenames.
- Source-isolated comparison cells, sentence-ID support spans, bounded missing-cell
  repair, and format-only re-rendering without new model calls.
- Upload replacement/removal/retry handling, Clear chat, progress and timing logs.
- 90 automated tests and a fresh 30-question real-PDF evaluation.

## Important limitations

This is an educational portfolio demo, not a verified-answer service. Reference
membership, exact support spans and acronym checks do not prove that a paraphrase
is correct. Evaluation still found misclassification and overgeneralization.
Source PDFs can be wrong or contradictory. Verify study-critical claims against
the original material; do not upload sensitive documents to the public demo.

Text-based PDFs only: no OCR, no reliable diagram extraction, no exhaustive
whole-book coverage. Limits are 5 PDFs, 20 MB combined and 500 pages combined.
Indexes are session-local and ephemeral. Generation quotas are shared; unlimited
traffic and production concurrency are not supported. Final-build Cloud load
testing remains unperformed.

## Evidence and release decision

See [the evaluation report](evaluations/v1-release-2026-10-11.md). The owner
explicitly chose a learning-demo release with documented answer-quality
limitations. Earlier strict answer-quality gates have not been declared passed.

## Next phase

Evaluate hybrid retrieval and reranking against this baseline, then query
rewriting/expansion and parent-child retrieval where useful. OCR/multimodal input,
FastAPI/frontend separation, and bounded corrective or agentic workflows are later
extensions, not features claimed by v1.0.
