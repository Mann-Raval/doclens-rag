import unittest

from langchain_core.documents import Document

from src.pdf_rag.pipeline import _citation_warning, _render_evidence_ids


class CitationFormatTests(unittest.TestCase):
    def setUp(self):
        self.docs = [Document(page_content="Evidence", metadata={"source": "notes.pdf", "page": i}) for i in range(3)]

    def test_explicit_groups_ranges_and_whitespace(self):
        for citation in ("[S1; S2; S3]", "[ S1, S2, S3 ]", "[S1-S3]", "[S1–S2; S3]"):
            rendered = _render_evidence_ids(citation, self.docs)
            self.assertEqual(rendered, "[notes.pdf, Page 1] [notes.pdf, Page 2] [notes.pdf, Page 3]")
            self.assertEqual(_citation_warning(rendered, self.docs), "")

    def test_invalid_ids_and_ranges_are_not_repaired(self):
        for citation in ("[S1-S99]", "[S3-S1]", "[ S99 ]", "[S0]", "[S1; S99]"):
            self.assertEqual(_render_evidence_ids(citation, self.docs), citation)
            self.assertIn("unknown", _citation_warning(citation, self.docs))

    def test_plain_numbers_are_not_guessed_as_evidence(self):
        self.assertEqual(_render_evidence_ids("Values [1, 2, 3]", self.docs), "Values [1, 2, 3]")
