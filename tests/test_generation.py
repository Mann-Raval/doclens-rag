import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from src.pdf_rag import pipeline
from src.pdf_rag.generation import response_details
from src.pdf_rag.retrieval import PdfIndex


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.index = PdfIndex.from_documents([
            Document(page_content="Ethernet uses frames.", metadata={"source": "a.pdf", "page": 0})
        ], backend="lexical")

    def test_token_limit_retries_once_and_retains_metadata(self):
        chain = Mock()
        chain.invoke.side_effect = [
            AIMessage(content="Partial", response_metadata={"finish_reason": "MAX_TOKENS"}),
            AIMessage(content="Ethernet uses frames [a.pdf, Page 1].", response_metadata={"finish_reason": "STOP"}),
        ]
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            result = pipeline.answer_question("What does Ethernet use?", self.index)
        self.assertEqual(chain.invoke.call_count, 2)
        self.assertEqual(result.finish_reason, "STOP")
        self.assertEqual(result.attempts, 2)
        self.assertFalse(result.warning)
        self.assertEqual(result.evidence[0]["text"], "Ethernet uses frames.")

    def test_repeated_truncation_is_visible_and_bounded(self):
        chain = Mock()
        chain.invoke.return_value = AIMessage(content="Partial", response_metadata={"finish_reason": "MAX_TOKENS"})
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            result = pipeline.answer_question("Ethernet?", self.index)
        self.assertEqual(chain.invoke.call_count, 2)
        self.assertIn("incomplete", result.warning)

    def test_safety_block_is_not_retried(self):
        chain = Mock()
        chain.invoke.return_value = AIMessage(content="", response_metadata={"finish_reason": "SAFETY"})
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            with self.assertRaisesRegex(RuntimeError, "SAFETY"):
                pipeline.answer_question("Ethernet?", self.index)
        self.assertEqual(chain.invoke.call_count, 1)

    def test_content_blocks_and_usage_are_preserved(self):
        response = AIMessage(content=[{"type": "text", "text": "An answer"}],
                             response_metadata={"finish_reason": "STOP"},
                             usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13})
        text, reason, usage = response_details(response)
        self.assertEqual(text, "An answer")
        self.assertEqual(usage["total_tokens"], 13)
