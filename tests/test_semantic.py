"""Exercise real Chroma plumbing offline with controlled vectors."""
import unittest
from langchain_core.documents import Document
from src.pdf_rag.retrieval import PdfIndex


class TopicEmbeddings:
    def __call__(self, input):
        return [[1.0, 0.0] if 'network' in text else [0.0, 1.0] for text in input]

    def embed_query(self, input):
        return self(input)

    @staticmethod
    def name():
        return 'doclens-test-topics'


class SemanticTests(unittest.TestCase):
    def test_similarity_and_collection_isolation(self):
        docs = [Document(page_content='fruit orchard'), Document(page_content='network frames')]
        first = PdfIndex.from_documents(docs, backend='semantic', embedding_function=TopicEmbeddings())
        second = PdfIndex.from_documents([Document(page_content='network private')], backend='semantic', embedding_function=TopicEmbeddings())
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        self.assertEqual(first.retrieve('network')[0].page_content, 'network frames')
        self.assertEqual(second.retrieve('network')[0].page_content, 'network private')
        first.close()
        self.assertEqual(second.collection.count(), 1)
