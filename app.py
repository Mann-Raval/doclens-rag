"""Streamlit interface for the PDF RAG assistant."""

import hashlib
import os
import tempfile

import streamlit as st

from rag import answer_question, process_pdfs

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


def process_uploads(uploaded_files) -> None:
    """Process selected uploads together and always remove temporary files."""
    digest = hashlib.sha256()
    uploads = []
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        uploads.append((uploaded_file.name, file_bytes))
        digest.update(len(uploaded_file.name).to_bytes(4, "big"))
        digest.update(uploaded_file.name.encode("utf-8"))
        digest.update(len(file_bytes).to_bytes(8, "big"))
        digest.update(file_bytes)
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
            with st.spinner(f"Reading and indexing {len(uploaded_files)} PDF(s)..."):
                process_uploads(uploaded_files)
        except Exception as error:
            st.session_state.pdf_index = None
            st.error(f"Could not process the selected PDFs: {error}")

    if st.session_state.pdf_index is not None:
        st.success(f"Ready: {len(st.session_state.pdf_names)} PDF(s)")
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
        (first, "📋 Summarize the document", "Summarize the document"),
        (first, "📚 Show the main topics", "What are the main topics covered?"),
        (second, "💡 What are the key takeaways?", "What are the key takeaways?"),
        (second, "🔎 Explain the core concept", "Explain the core concept of this document"),
    )
    for column, label, question in suggestions:
        with column:
            if st.button(label, use_container_width=True, disabled=not pdf_ready):
                st.session_state.messages.append({"role": "user", "content": question})
                st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            st.caption("Sources: " + "; ".join(message["sources"]))

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    question = st.session_state.messages[-1]["content"]
    history = st.session_state.messages[:-1]
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the document..."):
                result = answer_question(question, st.session_state.pdf_index, history)
            st.markdown(result.text)
            if result.sources:
                st.caption("Sources: " + "; ".join(result.sources))
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
