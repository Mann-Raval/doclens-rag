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

## Networking-chapter regression run

`network_cases.py` defines 30 prompts: 8 factual, 5 follow-up, 5 summary,
8 comparison, and 4 missing-information questions. It includes the original
failing comparison prompt and explicit review criteria.

```powershell
python -m evaluations.run_network --pdf-dir "PATH_TO_CN_FOLDER"
```

The folder must contain the three `CHAPTER*.pdf` course files. This command
sends selected passages to Gemini using your configured key and consumes API
quota. The private JSON report is saved under ignored `evaluations/local-results/`.
It records document hashes, answers, evidence, finish reasons, attempts, usage,
indexing time, first-text latency, and total latency. It stops on an API failure.
Use `--output evaluations/local-results/another-run.json` to retain separate runs.
Use `--start 22` to begin at case 22 after quota reset; `--limit` sets the last
case ID (default 30). Existing output files are never overwritten.
The runner does not automatically score correctness or citation entailment.
Follow-up cases provide a previous user question, not a complete live chat;
multi-turn browser testing remains a separate release check.

## Semantic smoke check

Run `python -m evaluations.semantic_smoke` to check real MiniLM + Chroma
retrieval without calling Gemini. It downloads the ONNX model on first use and
tests whether "doctor" retrieves a passage about a "physician". This passed on
the development machine with 384-dimensional embeddings. It is a plumbing and
paraphrase smoke check, not a general retrieval benchmark.
