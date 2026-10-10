import json
import unittest
from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from src.pdf_rag.source_comparison import compare_sources, comparison_cells, requested_source_chunks, validated_quotes


class SourceComparisonTests(unittest.TestCase):
    def test_explicit_chapters_exclude_other_files(self):
        docs = [Document(page_content="text", metadata={"source": f"CHAPTER-{i} notes.pdf"}) for i in (1, 2, 3)]
        self.assertEqual(requested_source_chunks(docs, "Compare chapter 1 with chapter 2"), docs[:2])
        self.assertEqual(requested_source_chunks(docs, "Compare chapters 1 and 2"), docs[:2])
        self.assertEqual(requested_source_chunks(docs, "Compare all three documents"), docs)
        self.assertEqual(requested_source_chunks(docs, "Compare chapter 9"), [])

    def setUp(self):
        self.docs = [
            Document(page_content="Networks connect computers. Network routing uses paths.", metadata={"source": "a.pdf"}),
            Document(page_content="Checksums detect errors. TCP uses checksums.", metadata={"source": "b.pdf"}),
        ]
        self.payload = {"context": "ignored", "history": "untrusted previous answer", "question": "Compare PDFs"}

    def test_invalid_id_wrong_source_and_paraphrase_are_rejected(self):
        evidence = {"S1": self.docs[0]}
        rows = [{"id": "S2", "quote": "Checksums detect errors."},
                {"id": "S1", "quote": "Checksums detect errors."},
                {"id": "S1", "quote": "Networks connect many computers."},
                {"id": "S1", "quote": "Networks connect computers."}]
        self.assertEqual(validated_quotes(json.dumps(rows), evidence, 30), [("S1", "Networks connect computers.")])

    def test_malformed_or_non_list_json_fails_closed(self):
        for raw in ("bad", "null", '{}', '[null, 1, "bad"]'):
            self.assertEqual(validated_quotes(raw, {"S1": self.docs[0]}, 30), [])

    def test_each_call_sees_one_source_and_only_validated_text_streams(self):
        chain = Mock()
        chain.invoke.side_effect = [
            json.dumps([{"feature": "Main focus", "summary": "Network connectivity", "evidence": [{"id":"S1","quote":"Networks connect computers."}]}]),
            json.dumps([{"feature": "Main focus", "summary": "Error detection", "evidence": [{"id":"S2","quote":"Checksums detect errors."}]}]),
        ]
        updates = []
        text, _, warning, calls = compare_sources(chain, self.docs, self.payload, table=True, on_update=updates.append)
        self.assertEqual(calls, 2)
        first, second = [call.args[0] for call in chain.invoke.call_args_list]
        self.assertNotIn("Checksums", first["context"])
        self.assertNotIn("Networks", second["context"])
        self.assertEqual(first["history"], "(none)")
        self.assertIn('Network connectivity [S1]', text)
        self.assertIn('Error detection [S2]', text)
        self.assertIn('| Feature | a.pdf | b.pdf |', text)
        self.assertNotIn('“Networks connect computers.”', text)
        self.assertEqual(updates[-1], text)
        self.assertEqual(warning, "")

    def test_no_valid_quotes_does_not_render_fabricated_answer(self):
        chain = Mock()
        chain.invoke.return_value = '[{"id":"S1","quote":"Both PDFs explain checksums."}]'
        text, _, warning, _ = compare_sources(chain, self.docs, self.payload)
        self.assertNotIn("Both PDFs explain", text)
        self.assertIn("No supported", warning)

    def test_word_budget_and_duplicate_quotes(self):
        row = {"id": "S1", "quote": "Networks connect computers."}
        self.assertEqual(len(validated_quotes(json.dumps([row, row]), {"S1": self.docs[0]}, 3)), 1)
        self.assertEqual(validated_quotes(json.dumps([row]), {"S1": self.docs[0]}, 2), [])

    def test_supported_quote_from_wrong_file_cannot_enter_cell(self):
        raw = json.dumps([{"feature": "Main focus", "summary": "Errors", "evidence": [{"id": "S2", "quote": "Checksums detect errors."}]}])
        self.assertEqual(comparison_cells(raw, {"S1": self.docs[0]}, ("Main focus",), 30), [])

    def test_unknown_reference_cell_is_not_rendered(self):
        chain = Mock()
        cell = {"feature": "Main focus", "summary": "Both files guarantee reliability", "evidence": [{"id": "S99"}]}
        chain.invoke.return_value = json.dumps([cell])
        text, _, warning, _ = compare_sources(chain, self.docs[:1], self.payload, table=True)
        self.assertNotIn("guarantee reliability", text)
        self.assertIn("Not established", text)
        self.assertTrue(warning)

    def test_provider_block_is_not_reported_as_success_or_retried(self):
        chain = Mock()
        chain.invoke.return_value = AIMessage(content="", response_metadata={"finish_reason": "SAFETY"})
        with self.assertRaisesRegex(RuntimeError, "SAFETY"):
            compare_sources(chain, self.docs, self.payload)
        chain.invoke.assert_called_once()
