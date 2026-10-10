"""PDF parsing and chunking."""
import os
import re
import hashlib
import time
from typing import Callable, Sequence
from pypdf import PdfReader
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .config import MAX_TOTAL_PAGES
from .retrieval import PdfIndex
from .metrics import log_metrics

def process_pdf(file_path: str) -> PdfIndex:
    """Backward-compatible helper for indexing one PDF."""
    return process_pdfs([(file_path, os.path.basename(file_path))])


def process_pdfs(
    files: Sequence[tuple[str, str]],
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> PdfIndex:
    """Load, chunk, and locally index several PDFs as one knowledge base."""
    if not files:
        raise ValueError("Select at least one PDF.")

    started = time.perf_counter()
    total_pages = 0
    for position, (file_path, _) in enumerate(files):
        if on_progress:
            on_progress("Checking PDF page counts", position, len(files))
        # Count the page tree before extracting any text from any file.
        with open(file_path, "rb") as stream:
            reader = PdfReader(stream)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("Password-protected PDFs must be unlocked before uploading.")
            total_pages += len(reader.pages)
        if total_pages > MAX_TOTAL_PAGES:
            raise ValueError(
                f"The selected PDFs exceed the {MAX_TOTAL_PAGES}-page limit. "
                "Upload fewer pages or split the PDF into smaller sections."
            )
    log_metrics("index_validation", seconds=round(time.perf_counter() - started, 3), pages=total_pages)

    started = time.perf_counter()
    pages_with_text: list[Document] = []
    unreadable_files: list[str] = []
    extracted_pages = 0
    if on_progress:
        on_progress("Extracting PDF text", 0, total_pages)
    for file_path, display_name in files:
        readable_pages = []
        for page in PyPDFLoader(file_path).lazy_load():
            extracted_pages += 1
            if on_progress and (extracted_pages % 10 == 0 or extracted_pages == total_pages):
                on_progress("Extracting PDF text", extracted_pages, total_pages)
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

    log_metrics("index_extraction", seconds=round(time.perf_counter() - started, 3), pages=extracted_pages)
    started = time.perf_counter()
    if on_progress:
        on_progress("Splitting text into passages", 0, 1)
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
    log_metrics("index_chunking", seconds=round(time.perf_counter() - started, 3), chunks=len(chunks))
    return PdfIndex.from_documents(chunks, on_progress=on_progress)
