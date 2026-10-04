# DocLens — Document Q&A with RAG

Status: Basic RAG foundation in progress. See [roadmap](docs/roadmap.md) and
[architecture](docs/architecture.md). Offline tests verify mechanics; real-document
answer quality has not yet been established by a benchmark.

A small retrieval-augmented generation (RAG) app built with Streamlit,
LangChain, local MiniLM embeddings, ChromaDB, and Gemini. Upload one or more text-based PDFs, ask detailed
questions, compare documents, and get answers grounded in retrieved passages
with filename-and-page citations.

## How the pipeline works

1. `PyPDFLoader` extracts text, filename, and page metadata from every PDF.
2. A recursive splitter creates overlapping chunks.
3. MiniLM (`all-MiniLM-L6-v2`, ONNX CPU) embeds chunks locally into ChromaDB.
4. The same model embeds the question; cosine similarity selects relevant chunks.
5. Gemini answers from those chunks and cites their page markers.

Summary-style questions sample chunks across every PDF rather than only
retrieving the first few semantic matches. Normal questions use semantic
retrieval, and the model can produce answers up to
4,096 tokens. Recent chat messages are supplied so follow-up questions have
context.

## Run locally

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` with `GOOGLE_API_KEY=your_key`. Optionally set `GEMINI_CHAT_MODEL`.
No Groq or embedding API key is required. First indexing downloads the embedding
model; later requests reuse its disk cache. `RETRIEVAL_BACKEND=lexical` enables
the old TF-IDF baseline for comparisons or offline tests.
Then run:

```powershell
streamlit run app.py
```

Scanned/image-only PDFs are not supported yet; run OCR on them before upload.
Changing the selected files rebuilds the in-memory index; ordinary Streamlit
reruns reuse the existing index. Uploaded temporary files are deleted immediately
after parsing. Each session owns a unique ephemeral Chroma collection. Replacement
and removal delete the old collection; abandoned indexes are cleaned when their
Python objects are collected. No document index survives server restarts.
Only model weights are cached on disk; uploads may also remain in Streamlit's
memory while selected. Never commit uploads, API keys, or model weights.

The app accepts up to five PDFs, 20 MB combined, and 500 pages per session. PDF
indexing consumes no Gemini quota. Each answered question still makes one Gemini
generation request normally, with one bounded retry for empty or token-limited
responses. A public deployment should use billing, authentication,
and application-level rate limiting rather than depending on a shared free key.

## Development

```powershell
python -m unittest discover -s tests -v
```

The interface remains in `app.py`. The backend modules are in `src/pdf_rag`;
`rag.py` preserves the existing public functions. The source panel exposes
retrieved excerpts, and incomplete model responses show a warning. See
[evaluation protocol](evaluations/README.md) for the quality checks still required.

## Streamlit Community Cloud

Deploy `app.py` from `Mann-Raval/doclens-rag`, branch
`feat/basic-rag-foundation`, using Python 3.12. Put `GOOGLE_API_KEY` in the app's
Secrets settings (top-level TOML), not in GitHub. See
[deployment instructions](docs/deployment.md). FastAPI and a separate frontend
are deferred to the next phase.
