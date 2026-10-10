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
| presentation | Safe table cleanup and answer-local numbered citation display |

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

Generation cites evidence IDs, which code maps to actual filename/page markers.
Grouped IDs are supported only when every ID is known. Explicit prose-word
limits override the detailed template and can trigger one bounded shortening
retry; citations are excluded from the prose count. Unknown references and
over-limit final answers retain visible warnings.

Format-only follow-ups such as "make difference table" retain the last
substantive user question. Explicitly named new topics take precedence over
conversation history. Requested tables override the default prose comparison
layout; common "differnce" spelling is normalized for routing. A retry after
a formatting follow-up retains both the original subject and requested format.
Collection-summary follow-ups retain collection-wide retrieval. Without a prior
subject, a generic table request defaults to the uploaded documents. A prior
explicit topic (e.g. TCP/UDP) remains topic-scoped. Table prompts exclude prior
assistant answers to avoid copying earlier failed output as evidence.

Display formatting replaces repeated filename/page citations with compact
numbers, grouped and deduplicated when adjacent. The source expander maps each
number back to its full filename/page and flags references absent from retrieved
evidence. Original text is retained for history and diagnostics. Streaming and
saved answers use the same formatter; numbers reset for each answer. HTML break
tags become semicolons inside table rows and paragraph breaks in prose, without
enabling unsafe HTML. Code fences are preserved. This is presentation cleanup,
not a claim-support validator.

Known limitations: sparse sampling for summaries; no OCR;
no entailment verification of citations; no authentication or production quotas.
Model output quality still requires evaluation on real PDFs.

## Feature-aligned document comparisons (build 1.3.10)

Explicit filenames/chapter numbers restrict the source set. Each file receives
one isolated model call producing JSON cells for shared features: main focus,
key concepts, mechanisms/methods, and examples. Short word-limited requests use
two rows. Cells contain concise paraphrases and evidence IDs, not pasted quotes.

The application validates schema, word bounds, feature labels, and ownership of
every cited ID before rendering columns per document and rows per feature. IDs
from another file are rejected. A missing cell says its content was not established
by retrieved evidence; this is not a claim that the PDF lacks the topic. Formatting
follow-ups retain source scope. Output is published after the source calls finish;
unvalidated intermediate JSON is never streamed into the answer.

An experimental second LLM review rejected useful content, was inconsistent,
and added latency; it is not shipped. This path validates reference membership,
NOT semantic entailment or factual truth. Generated paraphrases can still be
incorrect or incompletely supported, and source notes may themselves be wrong.
The quote-dump fallback from 1.3.8/1.3.9 has been removed. Other question routes
retain their existing behaviour and limitations.
