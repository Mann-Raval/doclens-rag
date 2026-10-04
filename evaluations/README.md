# Evaluation protocol

Basic RAG is not complete until real document answers have been reviewed.

Build 30 cases from PDFs that may legally be used for testing. For each record:

| Field | Meaning |
| --- | --- |
| question | Exact user input |
| history | Earlier turns for follow-ups |
| document_ids | Files in scope, identified by content hash |
| expected_pages | Pages containing supporting evidence |
| expected_facts | Facts the answer must contain |
| answerable | Whether the documents contain the answer |
| task | factual, follow-up, summary, comparison, or absent |

Record retrieved evidence, model name, finish reason, latency, token usage,
attempt count, factual correctness, citation validity, and completeness.
Compare lexical and semantic retrieval on the same cases. A reference that exists
is not necessarily evidence for the claim attached to it.

Do not commit API keys, private uploads, or copyrighted course PDFs. The unit
suite creates its own small PDF for ingestion checks; it does not evaluate
Gemini's answer quality. No model-quality score is claimed yet.

## Semantic smoke check

Run `python -m evaluations.semantic_smoke` to check real MiniLM + Chroma
retrieval without calling Gemini. It downloads the ONNX model on first use and
tests whether "doctor" retrieves a passage about a "physician". This passed on
the development machine with 384-dimensional embeddings. It is a plumbing and
paraphrase smoke check, not a general retrieval benchmark.
