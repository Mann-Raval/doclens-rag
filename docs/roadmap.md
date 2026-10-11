# DocLens milestones

Working branch: `feat/basic-rag-foundation`.
Starting commit: `83fd2b8` on `main` (verified against GitHub).

## Implemented in the foundation branch

- Modular pipeline with compatible Streamlit entry point.
- Paragraph-preserving text cleanup and chunk identifiers.
- Provider finish reason and usage retention.
- Bounded retry and visible incomplete-output warning.
- Inspectable retrieved excerpts.
- Tests using a generated PDF, independent of untracked course materials.
- Local MiniLM embeddings and session-isolated Chroma cosine search.

## v1.0 decision

The owner approved the basic-RAG **learning demo** release on 2026-10-11 with
documented limitations. See `evaluations/v1-release-2026-10-11.md` for the fresh
30-question run, 90 offline tests, selected claim review and Cloud observations.
This is not acceptance of the stronger production-quality gate below.

The foundation comprises three parts: ingestion (text extraction, cleanup,
chunking, metadata, indexing), retrieval (MiniLM, Chroma, similarity search and
document scope), and generation (context, answers, citations, chat follow-ups).
OCR is not implemented. Document-scope filtering is implemented; a general
user-configurable metadata-filter UI is not.

## Higher quality / production readiness still required

- Reproduce the failed comparisons on the original PDFs and inspect finish reasons.
- Load-test local embeddings and concurrent sessions on the selected host.
- Validate citation references and measure evidence support.
- Expand the evaluation corpus to 30 reviewed questions: factual, follow-up,
  summary, comparison, and absent-answer cases.
- Measure latency, answer completeness, supported claims, and retrieval quality.
- Verify upload replacement, retry, removal, and failure recovery in the UI.

Do not label offline unit tests as model-quality evaluations. Milestone tags
preserve the basic, hybrid, and agentic versions in the same repository.

## Next: advanced RAG

1. Freeze the v1 corpus, prompts and baseline results.
2. Evaluate hybrid lexical/semantic retrieval and reranking for evidence coverage.
3. Add query rewriting/expansion and parent-child retrieval only with measured gains.
4. Improve source parsing/OCR and claim-support evaluation as separate experiments.
5. Consider FastAPI/frontend separation and durable, user-owned storage.
6. Add bounded corrective or agentic workflows after their benefit is demonstrated.

Advanced retrieval is not a guarantee of correct generation. Retain the same
claim audits and negative/session-isolation checks when comparing milestones.
