# PDF RAG Assistant

A small retrieval-augmented generation (RAG) app built with Streamlit,
LangChain, Chroma, and Gemini. Upload one or more text-based PDFs, ask detailed
questions, compare documents, and get answers grounded in retrieved passages
with filename-and-page citations.

## How the pipeline works

1. `PyPDFLoader` extracts text, filename, and page metadata from every PDF.
2. A recursive splitter creates overlapping chunks.
3. Gemini creates embeddings and Chroma indexes them in memory.
4. Maximal marginal relevance retrieval selects relevant, varied chunks.
5. Gemini answers from those chunks and cites their page markers.

Summary-style questions sample chunks across every PDF rather than only
retrieving the first few semantic matches. Normal questions use diverse MMR
retrieval with a larger evidence set, and the model can produce answers up to
4,096 tokens. Recent chat messages are supplied so follow-up questions have
context.

## Run locally

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Put your Gemini key in `.env`, then run:

```powershell
streamlit run app.py
```

Scanned/image-only PDFs are not supported yet; run OCR on them before upload.
Changing the selected files rebuilds the in-memory index; ordinary Streamlit
reruns reuse the existing index and do not embed the PDFs again.
