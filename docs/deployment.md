# Deploy DocLens

Community Cloud hosts the Streamlit application. Chroma runs inside that app;
Community Cloud is not a managed vector database or durable document library.

1. Select repository `Mann-Raval/doclens-rag` and the tested feature branch
   `feat/basic-rag-foundation` (or main after merging).
2. Set entry point `app.py` and Python 3.12.
3. Add top-level secrets in the app's Advanced settings:

   ```toml
   GOOGLE_API_KEY = "your-key"
   GEMINI_CHAT_MODEL = "gemini-2.5-flash-lite"
   ```

4. Deploy. The first upload downloads MiniLM's ONNX model and takes longer.
5. Upload two small PDFs and verify factual questions, comparisons, citations,
   and independent sessions before sharing the app widely.

The host must reach the model download endpoint. No embedding API is used. Gemini
still has generation quotas shared by app users. This demo is not designed for
unlimited concurrent users. Session indexes and selected uploads consume RAM;
5 PDFs, 20 MB combined, and 500 pages are application limits, not hosting guarantees.

Indexes are ephemeral and rebuild after restarts. For durable libraries, move to
an external database/object store and implement user ownership and deletion.
Do not expose a shared persistent Chroma collection to anonymous visitors.

Official references:
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/develop/concepts/connections/connecting-to-data

Community Cloud resource limits can change. Its documentation explicitly states
local file persistence is not guaranteed. It is suitable for a portfolio demo,
not a guarantee of unlimited free traffic or permanent storage.
