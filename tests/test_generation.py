import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk
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

    def test_stream_preserves_complete_text_and_metadata(self):
        chain = Mock()
        chain.stream.return_value = iter([
            AIMessageChunk(content="Ethernet "),
            AIMessageChunk(content="uses frames.", response_metadata={"finish_reason": "STOP"},
                           usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13}),
        ])
        updates = []
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            result = pipeline.answer_question("Ethernet?", self.index, on_update=updates.append)
        self.assertEqual(result.text, "Ethernet uses frames.")
        self.assertEqual(updates[-1], result.text)
        self.assertEqual(result.usage["total_tokens"], 13)
        self.assertEqual(result.finish_reason, "STOP")
        chain.invoke.assert_not_called()

    def test_stream_retry_replaces_partial_answer(self):
        chain = Mock()
        chain.stream.side_effect = [
            iter([AIMessageChunk(content="Partial", response_metadata={"finish_reason": "MAX_TOKENS"})]),
            iter([AIMessageChunk(content="Complete", response_metadata={"finish_reason": "STOP"})]),
        ]
        updates = []
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            result = pipeline.answer_question("Ethernet?", self.index, on_update=updates.append)
        self.assertEqual(updates, ["", "Partial", "", "Complete"])
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.text, "Complete")

    def test_broken_stream_propagates_without_silent_retry(self):
        def broken():
            yield AIMessageChunk(content="Partial")
            raise ConnectionError("Stream interrupted")
        chain = Mock()
        chain.stream.return_value = broken()
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            with self.assertRaises(ConnectionError):
                pipeline.answer_question("Ethernet?", self.index, on_update=lambda text: None)
        self.assertEqual(chain.stream.call_count, 1)

    def test_invalid_citation_is_flagged_not_silently_rewritten(self):
        chain = Mock()
        chain.invoke.return_value = "Ethernet uses frames [guide.pdf, Page 1]."
        with patch.object(pipeline, "_answer_chain", return_value=chain):
            result = pipeline.answer_question("Ethernet?", self.index)
        self.assertIn("do not match", result.warning)
        self.assertIn("guide.pdf", result.text)

    def test_topic_comparison_uses_search_not_whole_collection_sampling(self):
        chain = Mock()
        chain.invoke.return_value = "Ethernet uses frames [a.pdf, Page 1]."
        with patch.object(pipeline, "_answer_chain", return_value=chain), patch.object(
            self.index, "retrieve", wraps=self.index.retrieve
        ) as retrieve:
            pipeline.answer_question("Compare TCP and UDP", self.index)
        retrieve.assert_called_once_with("Compare TCP and UDP", broad=False)
        self.assertIn("Compare only the concepts", chain.invoke.call_args.args[0]["task_guidance"])
