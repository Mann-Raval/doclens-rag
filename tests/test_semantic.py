"""Exercise real Chroma plumbing offline with controlled vectors."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from src.pdf_rag.retrieval import PdfIndex
from src.pdf_rag import retrieval


class TopicEmbeddings:
    def __call__(self, input):
        return [[1.0, 0.0] if 'network' in text else [0.0, 1.0] for text in input]

    def embed_query(self, input):
        return self(input)

    @staticmethod
    def name():
        return 'doclens-test-topics'


class SemanticTests(unittest.TestCase):
    def test_concurrent_cold_start_publishes_one_initialized_client(self):
        started, release, second_entered = Event(), Event(), Event()
        client = object()

        def construct(**kwargs):
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release initialization")
            return client

        def second_request():
            second_entered.set()
            return retrieval._chroma_client()

        with patch.object(retrieval, "_shared_chroma_client", None), patch(
            "chromadb.EphemeralClient", side_effect=construct
        ) as factory, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(retrieval._chroma_client)
            try:
                self.assertTrue(started.wait(5))
                second = pool.submit(second_request)
                self.assertTrue(second_entered.wait(5))
                self.assertIsNone(retrieval._shared_chroma_client)
            finally:
                release.set()
            self.assertIs(first.result(timeout=5), client)
            self.assertIs(second.result(timeout=5), client)
            factory.assert_called_once()

    def test_failed_client_construction_is_not_cached(self):
        client = object()
        with patch.object(retrieval, "_shared_chroma_client", None), patch(
            "chromadb.EphemeralClient", side_effect=[RuntimeError("startup failed"), client]
        ) as factory:
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                retrieval._chroma_client()
            self.assertIsNone(retrieval._shared_chroma_client)
            self.assertIs(retrieval._chroma_client(), client)
            self.assertEqual(factory.call_count, 2)

    def test_similarity_and_collection_isolation(self):
        docs = [Document(page_content='fruit orchard'), Document(page_content='network frames')]
        progress = Mock()
        first = PdfIndex.from_documents(docs, backend='semantic', embedding_function=TopicEmbeddings(), on_progress=progress)
        progress.assert_any_call("Embedding and indexing passages", 2, 2)
        second = PdfIndex.from_documents([Document(page_content='network private')], backend='semantic', embedding_function=TopicEmbeddings())
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        self.assertEqual(first.retrieve('network')[0].page_content, 'network frames')
        self.assertEqual(second.retrieve('network')[0].page_content, 'network private')
        first.close()
        self.assertEqual(second.collection.count(), 1)
