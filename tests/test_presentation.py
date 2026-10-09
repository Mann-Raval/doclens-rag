import unittest
from src.pdf_rag.presentation import present_answer


class PresentationTests(unittest.TestCase):
    def test_compact_references_are_stable_deduplicated_and_lossless(self):
        text = "One [a.pdf, Page 1] [a.pdf, Page 1], [b.pdf, Page 3]. Two [a.pdf, Page 1]."
        display, references = present_answer(text)
        self.assertEqual(display, "One [1, 2]. Two [1].")
        self.assertEqual(references, ["[a.pdf, Page 1]", "[b.pdf, Page 3]"])

    def test_break_tags_do_not_break_table_rows(self):
        text = "| Topic | Details |\n| --- | --- |\n| A | One<br>• Two<BR />Three&lt;br&gt;Four |"
        display, _ = present_answer(text)
        self.assertNotIn("<br", display.lower())
        self.assertNotIn("&lt;br", display)
        self.assertEqual(len(display.splitlines()), 3)
        self.assertIn("One; Two; Three; Four", display)

    def test_prose_breaks_and_code_fences(self):
        display, references = present_answer("One<br>Two\n```html\n<br>[x.pdf, Page 2]\n```")
        self.assertTrue(display.startswith("One\n\nTwo"))
        self.assertIn("<br>[x.pdf, Page 2]", display)
        self.assertEqual(references, [])

    def test_references_reset_per_answer_and_streaming_prefix_is_stable(self):
        prefix = "One [a.pdf, Page 5]"
        self.assertEqual(present_answer(prefix)[0], "One [1]")
        self.assertEqual(present_answer(prefix + " Two [b.pdf, Page 1]")[0], "One [1] Two [2]")
        self.assertEqual(present_answer("Two [b.pdf, Page 1]")[0], "Two [1]")

    def test_unknown_references_are_not_discarded(self):
        display, references = present_answer("Claim [invented.pdf, Page 99].")
        self.assertEqual(display, "Claim [1].")
        self.assertEqual(references, ["[invented.pdf, Page 99]"])
