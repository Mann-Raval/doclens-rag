import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

import rag


class FakeVectorStore:
    def __init__(self, documents):
        self.documents = documents
        self.last_query = None

    def max_marginal_relevance_search(self, query, **_kwargs):
        self.last_query = query
        return self.documents


class FakeChain:
    def __init__(self):
        self.values = None

    def invoke(self, values):
        self.values = values
        return "A grounded answer [Page 2]."


class RagTests(unittest.TestCase):
    def test_included_pdf_can_be_chunked_and_retrieved(self):
        embedding = DeterministicFakeEmbedding(size=64)
        with patch.object(rag, "_embeddings", return_value=embedding):
            index = rag.process_pdfs(
                [
                    ("dl-curriculum.pdf", "curriculum-a.pdf"),
                    ("dl-curriculum.pdf", "curriculum-b.pdf"),
                ]
            )

        self.assertGreater(len(index.chunks), 0)
        self.assertTrue(all("page" in chunk.metadata for chunk in index.chunks))
        self.assertEqual(
            {chunk.metadata["source"] for chunk in index.chunks},
            {"curriculum-a.pdf", "curriculum-b.pdf"},
        )
        self.assertGreater(len(index.retrieve("neural networks")), 0)

    def test_answer_uses_history_and_reports_one_based_pages(self):
        documents = [
            Document(
                page_content="Evidence",
                metadata={"page": 1, "source": "guide.pdf"},
            )
        ]
        store = FakeVectorStore(documents)
        index = rag.PdfIndex(vector_store=store, chunks=documents)
        chain = FakeChain()

        history = [{"role": "user", "content": "Tell me about optimizers"}]
        with patch.object(rag, "_answer_chain", return_value=chain):
            result = rag.answer_question("How does it work?", index, history)

        self.assertIn("optimizers", store.last_query)
        self.assertIn("User: Tell me about optimizers", chain.values["history"])
        self.assertIn("[guide.pdf, Page 2]", chain.values["context"])
        self.assertEqual(result.pages, (2,))
        self.assertEqual(result.sources, ("guide.pdf · page 2",))

    def test_summary_sampling_covers_start_and_end(self):
        chunks = [Document(page_content=str(number)) for number in range(100)]
        sampled = rag._evenly_spaced_chunks(chunks, 10)

        self.assertEqual(len(sampled), 10)
        self.assertEqual(sampled[0].page_content, "0")
        self.assertEqual(sampled[-1].page_content, "99")

    def test_broad_sampling_includes_every_pdf(self):
        chunks = [
            Document(page_content=f"A{number}", metadata={"source": "a.pdf"})
            for number in range(20)
        ] + [
            Document(page_content=f"B{number}", metadata={"source": "b.pdf"})
            for number in range(20)
        ]

        sampled = rag._select_broad_chunks(chunks, 10)

        self.assertEqual(len(sampled), 10)
        self.assertEqual({doc.metadata["source"] for doc in sampled}, {"a.pdf", "b.pdf"})


if __name__ == "__main__":
    unittest.main()
