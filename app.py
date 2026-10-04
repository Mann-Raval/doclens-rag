"""Streamlit interface for the PDF RAG assistant."""

import hashlib
import os
import tempfile

import streamlit as st

from rag import answer_question, process_pdfs

MAX_PDFS = 5
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
st.set_page_config(page_title="PDF RAG Assistant", page_icon="📄", layout="wide")


def initialize_state() -> None:
    defaults = {
        "messages": [],
        "pdf_index": None,
        "pdf_hash": None,
        "pdf_names": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sources(sources) -> None:
    """Keep retrieval details available without overwhelming the answer."""
    if not sources:
        return
    with st.expander("View retrieved sources", expanded=False):
        for source in sources:
            st.caption(f"• {source}")


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
    if file_hash == st.session_state.pdf_hash:
        return

    temp_paths = []
    try:
        file_specs = []
        for display_name, file_bytes in uploads:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_bytes)
                temp_paths.append(temp_file.name)
                file_specs.append((temp_file.name, display_name))
        new_index = process_pdfs(file_specs)
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    st.session_state.pdf_index = new_index
    st.session_state.pdf_hash = file_hash
    st.session_state.pdf_names = [name for name, _ in uploads]
    st.session_state.messages = []


initialize_state()

with st.sidebar:
    st.title("📄 PDF RAG Assistant")
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
            st.session_state.pdf_index = None
            st.error(f"Could not process the selected PDFs: {error}")
    elif st.session_state.pdf_names:
        st.session_state.pdf_index = None
        st.session_state.pdf_hash = None
        st.session_state.pdf_names = []
        st.session_state.messages = []

    if st.session_state.pdf_index is not None:
        st.success(f"Ready: {len(st.session_state.pdf_names)} PDF(s)")
        chunk_count = len(st.session_state.pdf_index.chunks)
        st.caption(
            f"{chunk_count} chunks indexed locally — no embedding API quota used"
        )
        for pdf_name in st.session_state.pdf_names:
            st.caption(f"• {pdf_name}")

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("PDF RAG Assistant")
st.caption("Ask detailed questions, compare information, or summarize your PDFs.")

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
                st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        render_sources(message.get("sources", ()))

if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
    if st.button("↻ Regenerate last answer"):
        st.session_state.messages.pop()
        st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    question = st.session_state.messages[-1]["content"]
    history = st.session_state.messages[:-1]
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the document..."):
                result = answer_question(question, st.session_state.pdf_index, history)
            st.markdown(result.text)
            render_sources(result.sources)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.text,
                    "pages": result.pages,
                    "sources": result.sources,
                }
            )
        except Exception as error:
            st.error(f"I could not answer that question: {error}")

user_input = st.chat_input("Ask your PDF anything...", disabled=not pdf_ready)
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()
