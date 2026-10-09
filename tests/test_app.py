"""Exercise upload/session UI state with controlled indexing and generation.

PDF parsing and real collection isolation are covered separately. These tests
do not substitute for concurrent browser sessions on the deployed host.
"""
from io import BytesIO
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from src.pdf_rag.schemas import RagAnswer


def upload(name, content=b"pdf fixture"):
    item = BytesIO(content)
    item.name = name
    return item


def index():
    item = Mock()
    item.chunks = ["fixture"]
    return item


class AppLifecycleTests(unittest.TestCase):
    def test_compact_answer_and_source_legend_preserve_raw_history(self):
        app = AppTest.from_file("../app.py")
        uploads = [upload("a.pdf")]
        build = Mock(return_value=index())
        self.run_app(app, uploads, build)
        app.session_state.messages = [{"role": "user", "content": "Make a table"}]
        raw = "| Topic | Detail |\n| --- | --- |\n| A | First<br>Second [a.pdf, Page 1] |"
        result = RagAnswer(text=raw, pages=(1,), sources=("a.pdf, pages 1",),
                           evidence=({"source": "a.pdf", "page": 1, "text": "First Second"},))
        def generate(*args, **kwargs):
            kwargs["on_update"](raw)
            return result
        with patch("rag.answer_question", side_effect=generate):
            self.run_app(app, uploads, build)
        self.assertEqual(app.session_state.messages[-1]["content"], raw)
        for rerender in (False, True):
            if rerender:
                self.run_app(app, uploads, build)
            visible = "\n".join(item.value for item in app.markdown)
            self.assertIn("First; Second [1]", visible)
            self.assertNotIn("<br>", visible)
            self.assertIn("[1] a.pdf, Page 1", [item.value for item in app.text])

    def run_app(self, app, uploads, build):
        with patch("streamlit.file_uploader", return_value=uploads), patch("rag.process_pdfs", build):
            app.run()
        self.assertEqual(len(app.exception), 0)

    def test_upload_reuse_replacement_and_removal(self):
        app = AppTest.from_file("../app.py")
        first, second = index(), index()
        build = Mock(side_effect=[first, second])
        self.run_app(app, [upload("a.pdf")], build)
        self.run_app(app, [upload("a.pdf")], build)
        self.assertEqual(build.call_count, 1)
        self.run_app(app, [upload("a.pdf", b"changed contents")], build)
        first.close.assert_called_once()
        self.assertIs(app.session_state.pdf_index, second)
        app.session_state.answer_error = "old error"
        self.run_app(app, [], build)
        second.close.assert_called_once()
        self.assertIsNone(app.session_state.pdf_index)
        self.assertIsNone(app.session_state.answer_error)
        self.assertEqual(app.session_state.messages, [])

    def test_bad_replacement_does_not_answer_from_old_index(self):
        app = AppTest.from_file("../app.py")
        first = index()
        self.run_app(app, [upload("a.pdf")], Mock(return_value=first))
        self.run_app(app, [upload("b.pdf")], Mock(side_effect=ValueError("unreadable PDF")))
        first.close.assert_called_once()
        self.assertIsNone(app.session_state.pdf_index)
        self.assertTrue(app.chat_input[0].disabled)

    def test_sessions_have_independent_indexes_and_chat(self):
        one, two = AppTest.from_file("../app.py"), AppTest.from_file("../app.py")
        first, second = index(), index()
        self.run_app(one, [upload("a.pdf")], Mock(return_value=first))
        self.run_app(two, [upload("b.pdf")], Mock(return_value=second))
        one.session_state.messages = [{"role": "assistant", "content": "private"}]
        self.assertEqual(two.session_state.messages, [])
        self.run_app(one, [], Mock())
        second.close.assert_not_called()
        self.assertIs(two.session_state.pdf_index, second)

    def test_failed_generation_requires_explicit_retry(self):
        app = AppTest.from_file("../app.py")
        build = Mock(return_value=index())
        uploads = [upload("a.pdf")]
        self.run_app(app, uploads, build)
        app.session_state.messages = [{"role": "user", "content": "What is TCP?"}]
        generate = Mock(side_effect=ConnectionError("interrupted"))
        with patch("rag.answer_question", generate):
            self.run_app(app, uploads, build)
            self.run_app(app, uploads, build)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(len(app.session_state.messages), 1)
        retry = next(button for button in app.button if button.label == "Retry failed answer")
        retry.click()
        with patch("rag.answer_question", return_value=RagAnswer(text="Complete", pages=())) as generate:
            self.run_app(app, uploads, build)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(app.session_state.messages[-1]["content"], "Complete")
