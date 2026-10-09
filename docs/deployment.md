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
   DOCLENS_METRICS = "1"
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

## Release validation on the deployed host

Use [Streamlit's deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
to create the app from your signed-in account. Never commit secrets to GitHub.

With `DOCLENS_METRICS="1"`, application logs include indexing time, answer time,
time to first nonempty text, finish reason, and Linux process RSS snapshots.
They exclude questions, filenames, source text, and keys. RSS is for the entire
app process, not one session or peak RAM. Unsupported platforms report null RSS.

Record deployment URL, commit, Python version, upload sizes/page counts, and:

- One cold upload and at least five warm uploads/questions, reporting p50/p95
  time to first text and total time. Do not call local timings Cloud measurements.
- Two browsers/incognito sessions using different PDFs. Ask each about a unique
  fact in the other session's PDF; verify there is no cross-session evidence.
- Replace and remove uploads; verify old chat/index state is cleared.
- Retry a failed answer and regenerate a completed answer; inspect streaming,
  warnings, finish reasons, and evidence.
- Observe process RSS before/after upload, two active sessions, and removal.
  Memory may be retained by Python/ONNX allocators even after collection deletion.

Do not merge/tag `v1.0` until answer-quality review and these deployed checks
are recorded. The feature branch can be deployed as a release candidate first.
