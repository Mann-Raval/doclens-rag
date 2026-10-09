# Basic RAG foundation

Streamlit (`app.py`) calls the compatibility entry point (`rag.py`). Services
live in `src/pdf_rag`:

| Module | Responsibility |
| --- | --- |
| config | Shared limits |
| ingestion | Parse PDF pages, preserve line breaks, split, assign chunk IDs |
| embeddings | Shared MiniLM ONNX model running on CPU |
| retrieval | Session-isolated Chroma similarity search; optional TF-IDF baseline |
| generation | Gemini prompt, model creation, response metadata extraction |
| pipeline | Route question, collect evidence, generate, handle bounded retry |
| schemas | Answer, evidence, warning and diagnostic fields |
| metrics | Opt-in content-free timing and process-memory logs |

Indexes are session-scoped ephemeral Chroma collections in server RAM. Temporary parsing files
are removed after ingestion; Streamlit may retain uploaded bytes while selected.
Text used for generation is sent to Gemini. Local indexing does not mean fully
local inference. MiniLM weights are cached on server disk after the first download.
Documents and queries use the same embedding model. Collection names are unique
per upload set and are deleted on replacement/removal and object finalization.
Unchanged uploads reuse the existing session index. There is no cross-user cache.

Generation uses one request normally. A token-limit or empty STOP/UNKNOWN response
gets at most one application-level retry requesting a shorter answer. Safety
responses are not retried. Transport retries inside the provider SDK are separate.
Finish reasons and token usage are retained. A second truncated response is
displayed with a warning; this is not proof that STOP responses are factually
complete. The actual retrieved passages are available in the source panel.

Streaming publishes accumulated text snapshots while preserving model metadata.
A regeneration clears the previous partial display; stream exceptions propagate
to the explicit retry UI instead of saving partial text as a completed answer.
Specific questions and topic comparisons use semantic retrieval. Whole-document
comparisons use balanced sampling, with document-focused comparison guidance.
Citation-marker membership is checked and missing/invalid markers are flagged;
this check does not establish that the cited passage supports the claim.

Known limitations: sparse sampling for summaries; no OCR;
no entailment verification of citations; no authentication or production quotas.
Model output quality still requires evaluation on real PDFs.
