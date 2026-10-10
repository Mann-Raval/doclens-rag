import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

from src.pdf_rag import pipeline as rag


class FakeChain:
    def __init__(self):
        self.values = None

    def invoke(self, values):
        self.values = values
        return "A grounded answer [Page 2]."


class RagTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"RETRIEVAL_BACKEND": "lexical"})
        env.start()
        self.addCleanup(env.stop)

    def test_included_pdf_can_be_chunked_and_retrieved(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            writer = PdfWriter()
            page = writer.add_blank_page(width=300, height=300)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 30 200 Td (Neural networks learn from examples.) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
            writer.write(path)
            index = rag.process_pdfs([(str(path), "curriculum-a.pdf"),
                                      (str(path), "curriculum-b.pdf")])

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
        index = rag.PdfIndex.from_documents(documents)
        chain = FakeChain()

        history = [{"role": "user", "content": "Tell me about optimizers"}]
        with patch.object(rag, "_answer_chain", return_value=chain):
            result = rag.answer_question("How does it work?", index, history)

        self.assertIn("optimizers", rag._build_retrieval_query("How does it work?", history))
        self.assertIn("User: Tell me about optimizers", chain.values["history"])
        self.assertIn("[guide.pdf, Page 2]", chain.values["context"])
        self.assertEqual(result.pages, (2,))
        self.assertEqual(result.sources, ("guide.pdf, pages 2",))

    def test_summary_question_receives_explicit_synthesis_guidance(self):
        documents = [
            Document(
                page_content="The protocol uses collision detection.",
                metadata={"page": 0, "source": "network.pdf"},
            )
        ]
        index = rag.PdfIndex.from_documents(documents)
        chain = FakeChain()

        with patch.object(rag, "_answer_chain", return_value=chain):
            rag.answer_question("What are the key takeaways?", index)

        self.assertIn("synthesis request", chain.values["task_guidance"])
        self.assertIn("instead of replying that the answer is unknown", chain.values["task_guidance"])

    def test_comparison_question_receives_comparison_specific_guidance(self):
        documents = [
            Document(
                page_content="Ethernet uses frames.",
                metadata={"page": 0, "source": "ethernet.pdf"},
            ),
            Document(
                page_content="TCP provides reliable transport.",
                metadata={"page": 0, "source": "tcp.pdf"},
            ),
        ]
        index = rag.PdfIndex.from_documents(documents)
        chain = FakeChain()

        with patch.object(rag, "_answer_chain", return_value=chain):
            rag.answer_question(
                "Compare the uploaded PDFs, explaining their shared ideas and important differences.",
                index,
            )

        self.assertEqual(rag._question_mode("Compare the uploaded PDFs"), "comparison")
        self.assertIn("Copy each quote VERBATIM", chain.values["task_guidance"])
        self.assertIn("TCP provides reliable transport", chain.values["context"])
        self.assertNotIn("Ethernet uses frames", chain.values["context"])

    def test_retry_message_regenerates_previous_comparison(self):
        documents = [
            Document(
                page_content="Ethernet uses frames.",
                metadata={"page": 0, "source": "ethernet.pdf"},
            )
        ]
        index = rag.PdfIndex.from_documents(documents)
        chain = FakeChain()
        history = [
            {"role": "user", "content": "Compare the uploaded PDFs."},
            {"role": "assistant", "content": "Incomplete answer"},
            {"role": "user", "content": "it stopped"},
            {"role": "assistant", "content": "I don't know"},
        ]

        with patch.object(rag, "_answer_chain", return_value=chain):
            rag.answer_question("try again", index, history)

        self.assertEqual(chain.values["question"], "Compare the uploaded PDFs.")
        self.assertIn("previous response was incomplete", chain.values["task_guidance"])

    def test_missing_output_message_regenerates_previous_question(self):
        history = [
            {"role": "user", "content": "Compare the uploaded PDFs."},
            {"role": "assistant", "content": "Incomplete"},
        ]

        question, is_retry = rag._resolve_question("where is the output?", history)

        self.assertEqual(question, "Compare the uploaded PDFs.")
        self.assertTrue(is_retry)

    def test_comparison_context_is_capped_and_balanced(self):
        chunks = [
            Document(page_content=f"A{n}", metadata={"source": "a.pdf"})
            for n in range(50)
        ] + [
            Document(page_content=f"B{n}", metadata={"source": "b.pdf"})
            for n in range(50)
        ]

        selected = rag._select_broad_chunks(chunks, rag.MAX_COMPARISON_CHUNKS)

        self.assertEqual(len(selected), 24)
        self.assertEqual(
            {source: sum(doc.metadata["source"] == source for doc in selected)
             for source in ("a.pdf", "b.pdf")},
            {"a.pdf": 12, "b.pdf": 12},
        )

    def test_every_suggestion_is_detected_as_a_broad_question(self):
        questions = (
            "Provide a detailed summary of each uploaded PDF.",
            "Identify and explain the main topics in each uploaded PDF.",
            "Derive the most important takeaways from each uploaded PDF.",
            "Compare the uploaded PDFs and explain their differences.",
        )

        self.assertTrue(all(rag._is_broad_document_question(q) for q in questions))

    def test_local_retrieval_ranks_relevant_text_without_an_api(self):
        documents = [
            Document(page_content="Bananas and mangoes are tropical fruit."),
            Document(page_content="Gradient descent optimizes a neural network."),
            Document(page_content="A database stores structured records."),
        ]
        index = rag.PdfIndex.from_documents(documents)

        results = index.retrieve("How does gradient descent optimize networks?")

        self.assertEqual(results[0].page_content, documents[1].page_content)

    def test_sources_are_grouped_by_pdf_and_page_range(self):
        documents = [
            Document(page_content="A", metadata={"source": "chapter.pdf", "page": 0}),
            Document(page_content="B", metadata={"source": "chapter.pdf", "page": 1}),
            Document(page_content="C", metadata={"source": "chapter.pdf", "page": 2}),
            Document(page_content="D", metadata={"source": "appendix.pdf", "page": 4}),
        ]

        labels = rag._source_labels(documents)

        self.assertEqual(
            labels,
            ("appendix.pdf, pages 5", "chapter.pdf, pages 1-3"),
        )

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
