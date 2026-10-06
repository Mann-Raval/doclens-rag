# Basic RAG milestone

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

## Required before calling Basic RAG complete

- Reproduce the failed comparisons on the original PDFs and inspect finish reasons.
- Load-test local embeddings and concurrent sessions on the selected host.
- Validate citation references and measure evidence support.
- Expand the evaluation corpus to 30 reviewed questions: factual, follow-up,
  summary, comparison, and absent-answer cases.
- Measure latency, answer completeness, supported claims, and retrieval quality.
- Verify upload replacement, retry, removal, and failure recovery in the UI.

Do not label offline unit tests as model-quality evaluations. Keep the current
main branch available while this work is reviewed. Later milestone tags can
preserve the basic, hybrid, and agentic versions without creating duplicate repos.
