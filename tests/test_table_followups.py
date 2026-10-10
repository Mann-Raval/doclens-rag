import unittest
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from src.pdf_rag import pipeline
from src.pdf_rag.retrieval import PdfIndex


class TableFollowupTests(unittest.TestCase):
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
        self.assertIn("Copy each quote VERBATIM", guidance)
        self.assertIn("| Document | Selected evidence |", answer.text)
        self.assertEqual(len(answer.sources), 3)
