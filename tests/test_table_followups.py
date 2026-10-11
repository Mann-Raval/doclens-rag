import unittest
import json
from dataclasses import asdict
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from src.pdf_rag import pipeline
from src.pdf_rag.retrieval import PdfIndex


class TableFollowupTests(unittest.TestCase):
    def test_short_table_phrases_and_typo_preserve_original_comparison(self):
        index, original, history = self.comparison_fixture()
        for query in ("in tabel form", "in table form", "in a table", "as a table",
                      "in tabular form", "please in table format", "in table form please"):
            with self.subTest(query=query), patch.object(
                pipeline, "_answer_chain", side_effect=AssertionError("Must reuse comparison")
            ):
                result = pipeline.answer_question(query, index, history)
                self.assertEqual(result.comparison, original.comparison)
                self.assertEqual(result.evidence, original.evidence)
                self.assertEqual(result.attempts, 0)
                self.assertIn("Chapter 2 original focus", result.text)
                self.assertNotIn("CHAPTER 3", result.text)
        for query in ("in table form compare TCP and UDP", "in a table compare chapter 3",
                      "What is a routing tabel?"):
            self.assertFalse(pipeline._is_format_followup(query))

    def test_chapter_typo_routes_and_scopes_the_comparison(self):
        query, _ = pipeline._resolve_question("make difference between chaoter 1 and chaoter 2", [])
        self.assertTrue(pipeline._cross_document_comparison(query))
        docs = [Document(page_content="text", metadata={"source": f"CHAPTER {i}.pdf"}) for i in (1, 2, 3)]
        self.assertEqual(pipeline.requested_source_chunks(docs, query), docs[:2])

    def comparison_fixture(self):
        index = PdfIndex.from_documents([
            Document(page_content=f"Chapter {i} evidence", metadata={"source": f"CHAPTER {i}.pdf", "page": i})
            for i in (1, 2)
        ], backend="lexical")
        chain = Mock()
        chain.invoke.side_effect = [json.dumps([{
            "feature": "Main focus", "summary": f"Chapter {i} original focus",
            "evidence": [{"id": f"S{i}"}],
        }]) for i in (1, 2)]
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            original = pipeline.answer_question("Compare chapter 1 with chapter 2", index)
        message = {**asdict(original), "role": "assistant", "content": original.text}
        history = [{"role": "user", "content": "Compare chapter 1 with chapter 2"}, message]
        return index, original, history

    def test_format_followup_preserves_cells_and_evidence_without_model_or_retrieval(self):
        index, original, history = self.comparison_fixture()
        updates = []
        with patch.object(pipeline, "_answer_chain", side_effect=AssertionError("No model call")), \
                patch.object(index, "retrieve", side_effect=AssertionError("No retrieval")):
            table = pipeline.answer_question("make difference table", index, history, on_update=updates.append)
            history.extend([{"role": "user", "content": "make difference table"},
                            {**asdict(table), "role": "assistant", "content": table.text}])
            repeated = pipeline.answer_question("table please", index, history)
        for i in (1, 2):
            self.assertIn(f"Chapter {i} original focus [CHAPTER {i}.pdf, Page {i + 1}]", table.text)
        self.assertEqual(table.evidence, original.evidence)
        self.assertEqual(table.sources, original.sources)
        self.assertEqual(table.comparison, original.comparison)
        self.assertEqual(table.attempts, 0)
        self.assertEqual(updates, [table.text])
        self.assertEqual(repeated.text, table.text)

    def test_comparison_snapshot_cannot_cross_sessions_or_replaced_uploads(self):
        index, _, history = self.comparison_fixture()
        replacement = PdfIndex.from_documents(index.chunks, backend="lexical")
        self.assertIsNone(pipeline._reformat_comparison("table", replacement, history))
        self.assertIsNone(pipeline._reformat_comparison("table", index, []))

    def test_new_topic_retry_and_intervening_answer_do_not_reuse_comparison(self):
        index, _, history = self.comparison_fixture()
        for query in ("try again", "Compare chapter 1 with chapter 3", "Compare TCP and UDP in a table"):
            self.assertIsNone(pipeline._reformat_comparison(query, index, history))
        history.extend([{"role": "user", "content": "Explain TCP"},
                        {"role": "assistant", "content": "TCP answer"}])
        self.assertIsNone(pipeline._reformat_comparison("table", index, history))

    def test_bare_table_requests_keep_chapter_scope(self):
        history = [{"role": "user", "content": '“Compare chapter 1 with chapter 2” and its table follow-up'}]
        for followup in ("difference table", "comparison table", "table", "table form", "the table please"):
            with self.subTest(followup=followup):
                resolved, _ = pipeline._resolve_question(followup, history)
                self.assertIn("Compare chapter 1 with chapter 2", resolved)
                self.assertTrue(pipeline._cross_document_comparison(resolved))
                self.assertTrue(pipeline._requests_table(resolved))
        explicit = "difference table between TCP and UDP"
        self.assertEqual(pipeline._resolve_question(explicit, history), (explicit, False))

    def test_screenshot_followup_uses_validated_table_and_only_two_chapters(self):
        index = PdfIndex.from_documents([
            Document(page_content=f"Chapter {i} contains its own evidence.", metadata={"source": f"CHAPTER {i}.pdf", "page": 0})
            for i in (1, 2, 3)
        ], backend="lexical")
        history = [{"role": "user", "content": '“Compare chapter 1 with chapter 2” and its table follow-up'},
                   {"role": "assistant", "content": "Earlier answer"}]
        chain = Mock()
        chain.invoke.side_effect = [json.dumps([{"feature": "Main focus", "summary": f"Chapter {i} evidence", "evidence": [{"id": f"S{i}"}]}]) for i in (1, 2)]
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            answer = pipeline.answer_question("difference table", index, history)
        self.assertEqual(chain.invoke.call_count, 2)
        self.assertIn("| Feature | CHAPTER 1.pdf | CHAPTER 2.pdf |", answer.text)
        self.assertNotIn("CHAPTER 3", answer.text)
        self.assertEqual(len(answer.sources), 2)
        self.assertEqual(answer.warning, "")

    def test_first_question_defaults_to_uploaded_documents(self):
        query, _ = pipeline._resolve_question("Make difference table", [])
        self.assertTrue(pipeline._cross_document_comparison(query))
        self.assertEqual(pipeline._question_mode(query), "comparison")

    def test_collection_summary_followups_keep_broad_scope(self):
        for previous in (
            "Provide a detailed summary of each uploaded PDF, followed by a combined overview.",
            "Identify and explain the main topics in each uploaded PDF.",
            "Derive the most important takeaways from each uploaded PDF and the collection overall.",
        ):
            query, _ = pipeline._resolve_question("Make difference table", [{"role": "user", "content": previous}])
            self.assertTrue(pipeline._cross_document_comparison(query), previous)
        query, _ = pipeline._resolve_question("Make difference table", [{"role": "user", "content": "Summarize TCP and UDP."}])
        self.assertFalse(pipeline._cross_document_comparison(query))

    def test_failed_assistant_history_is_not_used_as_table_template(self):
        index = PdfIndex.from_documents([Document(page_content="Evidence", metadata={"source": "a.pdf", "page": 0})], backend="lexical")
        chain = Mock()
        chain.invoke.return_value = "Answer [S1]"
        history = [{"role": "user", "content": "Summarize all documents."},
                   {"role": "assistant", "content": "I don't know based on the provided documents."}]
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            pipeline.answer_question("Make difference table", index, history)
        payload = chain.invoke.call_args.args[0]
        self.assertNotIn("I don't know", payload["history"])
        self.assertIn("Summarize all documents", payload["history"])

    def test_format_only_retains_prior_subject_and_retry_retains_format(self):
        history = [{"role": "user", "content": "Compare the uploaded PDFs."},
                   {"role": "assistant", "content": "Wrong HTTP answer"}]
        query, retry = pipeline._resolve_question("make difference table", history)
        self.assertIn("Compare the uploaded PDFs", query)
        self.assertIn("make difference table", query)
        self.assertFalse(retry)
        history.append({"role": "user", "content": "make difference table"})
        resolved, retry = pipeline._resolve_question("try again", history)
        self.assertEqual(resolved, query)
        self.assertTrue(retry)

    def test_explicit_chapter_table_with_typo_is_cross_document(self):
        query = "make differnce table of 3 chapters"
        self.assertEqual(pipeline._question_mode(query), "comparison")
        self.assertTrue(pipeline._cross_document_comparison(query))
        self.assertTrue(pipeline._requests_table(query))

    def test_explicit_topic_table_does_not_inherit_chapter_scope(self):
        history = [{"role": "user", "content": "Compare the uploaded PDFs."}]
        query = "Make a comparison table of TCP and UDP using these PDFs"
        self.assertEqual(pipeline._resolve_question(query, history), (query, False))
        self.assertFalse(pipeline._cross_document_comparison(query))
        self.assertFalse(pipeline._requests_table("What is a routing table?"))

    def test_table_prompt_retrieves_all_documents_and_removes_ban(self):
        index = PdfIndex.from_documents([
            Document(page_content=f"Chapter {i} material", metadata={"source": f"chapter{i}.pdf", "page": 0})
            for i in (1, 2, 3)
        ], backend="lexical")
        chain = Mock()
        chain.invoke.return_value = "| Document | Focus |\n| --- | --- |\n| Chapter 1 | Material [S1] |"
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            answer = pipeline.answer_question("make differnce table of 3 chapters", index)
        guidance = chain.invoke.call_args.args[0]["task_guidance"]
        self.assertNotIn("Do not use a Markdown table", guidance)
        self.assertIn("comparison cells for THIS document", guidance)
        self.assertIn("| Feature |", answer.text)
        self.assertEqual(len(answer.sources), 3)
