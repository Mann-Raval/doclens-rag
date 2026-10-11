"""Release routing matrix: equivalent language must not bypass source isolation."""
import unittest

from langchain_core.documents import Document

from src.pdf_rag.pipeline import _cross_document_comparison, _resolve_question, _is_format_followup
from src.pdf_rag.source_comparison import requested_source_chunks, synthesis_source_chunks


class ReleaseRoutingTests(unittest.TestCase):
    def test_polite_format_only_requests_do_not_change_topic(self):
        for query in ("can you put it in table form", "give it in a table", "make it a table",
                      "could you please show the same in tabular format", "format this as a table"):
            with self.subTest(query=query):
                self.assertTrue(_is_format_followup(query))
        self.assertFalse(_is_format_followup("can you compare TCP and UDP in table form"))
    def setUp(self):
        self.docs = [Document(page_content="text", metadata={"source": f"CHAPTER {i}.pdf"}) for i in (1, 2, 3)]

    def test_equivalent_two_chapter_comparisons_are_scoped(self):
        queries = (
            "give difference of chapter 1 and chapter 2 in table form",
            "show difference table of chaoter 1 and chapter 2 in table form",
            "Compare chapter 1 with chapter 2",
            "Contrast chapters 1 and 2",
            "Differentiate between chapters 1 and 2",
            "chapter 1 vs chapter 2",
            "chapter 1 versus 2",
            "compare chapters 1, 2",
            "difference between chapter-1 and chapter-2",
            "compare chapter 1 & 2",
            "comparison of CHAPTER 1.pdf and CHAPTER 2.pdf",
        )
        for query in queries:
            with self.subTest(query=query):
                resolved, _ = _resolve_question(query, [])
                self.assertTrue(_cross_document_comparison(resolved, self.docs))
                self.assertEqual(requested_source_chunks(self.docs, resolved), self.docs[:2])

    def test_document_collection_comparison_variants(self):
        for query in ("compare the uploaded PDFs", "differences of all documents",
                      "contrast the documents", "differences among these PDFs",
                      "how do these documents differ", "all differences between the PDFs"):
            with self.subTest(query=query):
                self.assertTrue(_cross_document_comparison(query, self.docs))

    def test_topic_and_inventory_requests_do_not_become_document_profiles(self):
        for query in ("Compare TCP and UDP using the uploaded PDFs",
                      "Compare TCP and UDP from chapter 3", "What is a routing table?",
                      "all differences in the PDF", "all comparisons in notes",
                      "Compare roles of the data link and network layers"):
            with self.subTest(query=query):
                self.assertFalse(_cross_document_comparison(query, self.docs))

    def test_explicit_filenames_are_document_targets(self):
        docs = [Document(page_content="text", metadata={"source": name})
                for name in ("alpha.pdf", "beta.pdf", "gamma.pdf")]
        query = "How does alpha.pdf differ from beta.pdf?"
        self.assertTrue(_cross_document_comparison(query, docs))
        self.assertEqual(requested_source_chunks(docs, query), docs[:2])

    def test_missing_requested_chapter_does_not_silently_compare_a_subset(self):
        self.assertEqual(requested_source_chunks(self.docs, "Compare chapter 1 and chapter 9"), [])
        self.assertEqual(requested_source_chunks(self.docs, "Compare CHAPTER 1.pdf with chapter 2"), self.docs[:2])

    def test_named_chapter_summary_does_not_pull_other_files(self):
        docs = [Document(page_content="text", metadata={"source": name}) for name in (
            "CHAPTER 1 Introduction to Computer Networks.pdf", "CHAPTER 2 Data Link and Network Layer.pdf",
            "CHAPTER-3 Transport LAYER.pdf")]
        self.assertEqual(synthesis_source_chunks(docs, "Summarize the transport and application layer chapter"), docs[2:])
        self.assertEqual(synthesis_source_chunks(docs, "Summarize chapter 2"), docs[1:2])
        self.assertEqual(synthesis_source_chunks(docs, "Summarize all documents"), docs)
