"""Compatibility entry point. Application services live in src/pdf_rag."""
from src.pdf_rag.pipeline import answer_question, get_answer
from src.pdf_rag.ingestion import process_pdf, process_pdfs
from src.pdf_rag.retrieval import PdfIndex
from src.pdf_rag.schemas import RagAnswer

__all__ = ["answer_question", "get_answer", "process_pdf", "process_pdfs", "PdfIndex", "RagAnswer"]
