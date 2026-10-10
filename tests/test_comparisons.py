import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from src.pdf_rag import pipeline
from src.pdf_rag.comparisons import comparison_passages, is_comparison_inventory
from src.pdf_rag.retrieval import PdfIndex


class ComparisonInventoryTests(unittest.TestCase):
    def test_inventory_differs_from_named_pair(self):
        self.assertTrue(is_comparison_inventory("give me all differences in notes so that i can learn for exam"))
        self.assertFalse(is_comparison_inventory("Give all differences between TCP and UDP"))
        self.assertFalse(is_comparison_inventory("Compare the uploaded PDFs"))

    def test_scan_covers_late_matches_and_context_is_bounded(self):
        docs = [Document(page_content=f"A versus B number {i}", metadata={"source": "a.pdf", "page": i}) for i in range(295)]
        selected = comparison_passages(docs)
        self.assertLessEqual(len(selected), 60)
        self.assertEqual(selected[0].metadata["page"], 0)
        self.assertEqual(selected[-1].metadata["page"], 294)

    def test_no_cues_still_returns_bounded_overview(self):
        docs = [Document(page_content="General notes", metadata={"source": "a.pdf", "page": i}) for i in range(100)]
        self.assertEqual(len(comparison_passages(docs)), 60)

    def test_table_followup_reuses_inventory_not_top_ten(self):
        docs = [Document(page_content="Ordinary text", metadata={"source": "notes.pdf", "page": i}) for i in range(295)]
        docs[20].page_content = "Symmetric versus asymmetric processing."
        docs[250].page_content = "Differences between paging and segmentation."
        index = PdfIndex.from_documents(docs, backend="lexical")
        history = [{"role": "user", "content": "give me all differences in notes so that i can learn for exam"},
                   {"role": "assistant", "content": "Only symmetric processing exists."}]
        chain = Mock()
        chain.invoke.return_value = "Comparisons found [S1]"
        with patch.object(pipeline, "_answer_chain", return_value=chain), patch.object(index, "retrieve") as retrieve:
            answer = pipeline.answer_question("all differences in table form", index, history)
        retrieve.assert_not_called()
        payload = chain.invoke.call_args.args[0]
        self.assertIn("Symmetric versus", payload["context"])
        self.assertIn("paging and segmentation", payload["context"])
        self.assertIn("Requested format: all differences in table form", payload["question"])
        self.assertNotIn("Only symmetric processing exists", payload["history"])
        self.assertIn("not a verified exhaustive list", answer.warning)
        self.assertTrue(pipeline._requests_table(payload["question"]))

    def test_inventory_table_without_history_is_not_file_comparison(self):
        query, _ = pipeline._resolve_question("all differences in table form", [])
        self.assertEqual(query, "all differences in table form")
        self.assertTrue(is_comparison_inventory(query))
