"""Streamlit interface for the PDF RAG assistant."""

import hashlib
import os
import tempfile
import time

import streamlit as st

from rag import answer_question, process_pdfs
from src.pdf_rag.metrics import log_metrics

MAX_PDFS = 5
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
APP_VERSION = "1.3.1"
st.set_page_config(page_title="DocLens", page_icon="📄", layout="wide")


def initialize_state() -> None:
    defaults = {
        "messages": [],
        "pdf_index": None,
        "pdf_hash": None,
        "pdf_names": [],
        "answer_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sources(sources, evidence=()) -> None:
    """Keep retrieval details available without overwhelming the answer."""
    if not sources:
        return
    with st.expander("View retrieved sources", expanded=False):
        for source in sources:
            st.caption(f"• {source}")
        for item in evidence:
            st.text(f"{item['source']} — page {item['page']}")
            st.text(item["text"])


def process_uploads(uploaded_files) -> None:
    """Process selected uploads together and always remove temporary files."""
    if len(uploaded_files) > MAX_PDFS:
        raise ValueError(f"Select at most {MAX_PDFS} PDFs at a time.")

    digest = hashlib.sha256()
    uploads = []
    total_bytes = 0
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        total_bytes += len(file_bytes)
        uploads.append((uploaded_file.name, file_bytes))
        digest.update(len(uploaded_file.name).to_bytes(4, "big"))
        digest.update(uploaded_file.name.encode("utf-8"))
        digest.update(len(file_bytes).to_bytes(8, "big"))
        digest.update(file_bytes)
    if total_bytes > MAX_UPLOAD_BYTES:
        raise ValueError("The PDFs must be 20 MB or less in total.")
    file_hash = digest.hexdigest()
    if file_hash == st.session_state.pdf_hash and st.session_state.pdf_index is not None:
        return

    temp_paths = []
    try:
        file_specs = []
        for display_name, file_bytes in uploads:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_bytes)
                temp_paths.append(temp_file.name)
                file_specs.append((temp_file.name, display_name))
        started = time.perf_counter()
        new_index = process_pdfs(file_specs)
        log_metrics("index", seconds=round(time.perf_counter() - started, 3),
                    documents=len(file_specs), chunks=len(new_index.chunks), upload_bytes=total_bytes)
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    if st.session_state.pdf_index is not None:
        st.session_state.pdf_index.close()
    st.session_state.pdf_index = new_index
    st.session_state.pdf_hash = file_hash
    st.session_state.pdf_names = [name for name, _ in uploads]
    st.session_state.messages = []
    st.session_state.answer_error = None


initialize_state()

with st.sidebar:
    st.title("📄 DocLens")
    st.caption("Answers grounded in your documents")
    st.divider()

    uploaded_files = st.file_uploader(
        "Upload one or more PDFs", type=["pdf"], accept_multiple_files=True
    )
    if uploaded_files:
        try:
            with st.spinner(
                f"Building a local index for {len(uploaded_files)} PDF(s)..."
            ):
                process_uploads(uploaded_files)
        except Exception as error:
            if st.session_state.pdf_index is not None:
                st.session_state.pdf_index.close()
            st.session_state.pdf_index = None
            st.error(f"Could not process the selected PDFs: {error}")
    elif st.session_state.pdf_names:
        if st.session_state.pdf_index is not None:
            st.session_state.pdf_index.close()
        st.session_state.pdf_index = None
        st.session_state.pdf_hash = None
        st.session_state.pdf_names = []
        st.session_state.messages = []
        st.session_state.answer_error = None

    if st.session_state.pdf_index is not None:
        st.success(f"Ready: {len(st.session_state.pdf_names)} PDF(s)")
        chunk_count = len(st.session_state.pdf_index.chunks)
        st.caption(
            f"{chunk_count} passages ready to search"
        )
        for pdf_name in st.session_state.pdf_names:
            st.caption(f"• {pdf_name}")

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.answer_error = None
        st.rerun()
    st.caption(f"Build {APP_VERSION}")

st.title("DocLens")
st.caption("Ask detailed questions, compare information, or summarize your PDFs.")
st.caption("Test version: verify important claims against the source excerpts. Cross-document comparisons can misattribute details.")

pdf_ready = st.session_state.pdf_index is not None
if not pdf_ready:
    st.info("Upload one or more text-based PDFs in the sidebar to begin.")

if not st.session_state.messages:
    first, second = st.columns(2)
    suggestions = (
        (
            first,
            "📋 Summarize all documents",
            "Provide a detailed summary of each uploaded PDF, followed by a combined overview.",
        ),
        (
            first,
            "📚 Show the main topics",
            "Identify and explain the main topics in each uploaded PDF.",
        ),
        (
            second,
            "💡 What are the key takeaways?",
            "Derive the most important takeaways from each uploaded PDF and the collection overall.",
        ),
        (
            second,
            "🔎 Compare the documents",
            "Compare the uploaded PDFs, explaining their shared ideas and important differences.",
        ),
    )
    for column, label, question in suggestions:
        with column:
            if st.button(label, use_container_width=True, disabled=not pdf_ready):
                st.session_state.messages.append({"role": "user", "content": question})
                st.session_state.answer_error = None
                st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("warning"):
            st.warning(message["warning"])
        render_sources(message.get("sources", ()), message.get("evidence", ()))

if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
    if st.button("↻ Regenerate last answer"):
        st.session_state.messages.pop()
        st.session_state.answer_error = None
        st.rerun()

if st.session_state.answer_error:
    st.error(st.session_state.answer_error)
    if st.button("Retry failed answer"):
        st.session_state.answer_error = None
        st.rerun()

if pdf_ready and not st.session_state.answer_error and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    question = st.session_state.messages[-1]["content"]
    history = st.session_state.messages[:-1]
    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        started = time.perf_counter()
        first_text = []
        def update_answer(text):
            if text and not first_text:
                first_text.append(time.perf_counter() - started)
            answer_placeholder.markdown(text + " ▌" if text else "")
        try:
            with st.spinner("Searching the document..."):
                result = answer_question(
                    question, st.session_state.pdf_index, history,
                    on_update=update_answer,
                )
            log_metrics("answer", seconds=round(time.perf_counter() - started, 3),
                        first_text_seconds=round(first_text[0], 3) if first_text else None,
                        attempts=result.attempts, finish_reason=result.finish_reason)
            answer_placeholder.markdown(result.text)
            if result.warning:
                st.warning(result.warning)
            render_sources(result.sources, result.evidence)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.text,
                    "pages": result.pages,
                    "sources": result.sources,
                    "evidence": result.evidence,
                    "warning": result.warning,
                    "finish_reason": result.finish_reason,
                    "usage": result.usage,
                }
            )
        except Exception as error:
            log_metrics("answer_error", seconds=round(time.perf_counter() - started, 3),
                        error_type=type(error).__name__)
            answer_placeholder.empty()
            st.session_state.answer_error = f"I could not answer that question: {error}"
            st.rerun()

user_input = st.chat_input("Ask your PDF anything...", disabled=not pdf_ready)
if user_input:
    st.session_state.answer_error = None
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()
