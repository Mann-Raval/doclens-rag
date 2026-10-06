"""PDF parsing and chunking."""
import os
import re
import hashlib
from typing import Sequence
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .config import MAX_TOTAL_PAGES
from .retrieval import PdfIndex

def process_pdf(file_path: str) -> PdfIndex:
    """Backward-compatible helper for indexing one PDF."""
    return process_pdfs([(file_path, os.path.basename(file_path))])


def process_pdfs(files: Sequence[tuple[str, str]]) -> PdfIndex:
    """Load, chunk, and locally index several PDFs as one knowledge base."""
    if not files:
        raise ValueError("Select at least one PDF.")

    pages_with_text: list[Document] = []
    unreadable_files: list[str] = []
    total_pages = 0
    for file_path, display_name in files:
        readable_pages = []
        for page in PyPDFLoader(file_path).lazy_load():
            total_pages += 1
            if total_pages > MAX_TOTAL_PAGES:
                raise ValueError(f"The selected PDFs exceed the {MAX_TOTAL_PAGES}-page limit.")
            # Preserve paragraph and line boundaries for the splitter.
            page.page_content = re.sub(r"[^\S\n]+", " ", page.page_content).strip()
            page.metadata["source"] = display_name
            if page.page_content.strip():
                readable_pages.append(page)
        if readable_pages:
            pages_with_text.extend(readable_pages)
        else:
            unreadable_files.append(display_name)

    if unreadable_files:
        names = ", ".join(unreadable_files)
        raise ValueError(
            f"No readable text was found in: {names}. Scanned PDFs need OCR first."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages_with_text)
    for position, chunk in enumerate(chunks):
        identity = f"{chunk.metadata['source']}:{chunk.metadata.get('page')}:{position}:{chunk.page_content}"
        chunk.metadata["chunk_id"] = hashlib.sha256(identity.encode()).hexdigest()[:24]

    # Local embeddings avoid external embedding API quotas.
    return PdfIndex.from_documents(chunks)
