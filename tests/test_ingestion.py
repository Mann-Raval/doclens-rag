"""Validate upload limits before expensive extraction or embedding."""
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch

from langchain_core.documents import Document

from src.pdf_rag.ingestion import process_pdfs


class IngestionTests(unittest.TestCase):
    def test_combined_page_limit_rejects_before_any_extraction(self):
        readers = [Mock(is_encrypted=False, pages=[None] * count) for count in (300, 201)]
        with patch("builtins.open", mock_open()), patch(
            "src.pdf_rag.ingestion.PdfReader", side_effect=readers
        ), patch("src.pdf_rag.ingestion.PyPDFLoader") as loader, patch(
            "src.pdf_rag.ingestion.PdfIndex.from_documents"
        ) as build:
            with self.assertRaisesRegex(ValueError, "500-page limit"):
                process_pdfs([("a", "a.pdf"), ("b", "b.pdf")])
            loader.assert_not_called()
            build.assert_not_called()

    def test_encrypted_pdf_rejected_before_extraction(self):
        reader = Mock(is_encrypted=True)
        reader.decrypt.return_value = 0
        with patch("builtins.open", mock_open()), patch(
            "src.pdf_rag.ingestion.PdfReader", return_value=reader
        ), patch("src.pdf_rag.ingestion.PyPDFLoader") as loader:
            with self.assertRaisesRegex(ValueError, "Password-protected"):
                process_pdfs([("a", "a.pdf")])
            loader.assert_not_called()

    def test_progress_preserves_page_metadata(self):
        reader = Mock(is_encrypted=False, pages=[None])
        loader = MagicMock()
        loader.lazy_load.return_value = iter([
            Document(page_content="Operating systems manage memory.", metadata={"page": 0})
        ])
        progress = Mock()
        with patch("builtins.open", mock_open()), patch(
            "src.pdf_rag.ingestion.PdfReader", return_value=reader
        ), patch("src.pdf_rag.ingestion.PyPDFLoader", return_value=loader), patch(
            "src.pdf_rag.ingestion.PdfIndex.from_documents"
        ) as build:
            process_pdfs([("a", "notes.pdf")], on_progress=progress)
            chunk = build.call_args.args[0][0]
            self.assertEqual(chunk.metadata["source"], "notes.pdf")
            self.assertEqual(chunk.metadata["page"], 0)
            self.assertIs(build.call_args.kwargs["on_progress"], progress)
            progress.assert_any_call("Extracting PDF text", 1, 1)
