"""Orchestrate retrieval, task routing, citations, and answer generation."""
import os
import re
from typing import Callable, Sequence
from langchain_core.documents import Document
from .config import MAX_HISTORY_MESSAGES, MAX_COMPARISON_CHUNKS
from .schemas import RagAnswer
from .retrieval import PdfIndex, _select_broad_chunks, _evenly_spaced_chunks
from .ingestion import process_pdf, process_pdfs
from .generation import _answer_chain, response_details

def answer_question(
    query: str,
    pdf_index: PdfIndex,
    chat_history: Sequence[dict[str, str]] | None = None,
    *,
    on_update: Callable[[str], None] | None = None,
) -> RagAnswer:
    """Retrieve supporting passages and generate a cited answer."""
    full_history = list(chat_history or [])
    history = full_history[-MAX_HISTORY_MESSAGES:]
    history_text = _format_history(history)
    effective_query, is_retry = _resolve_question(query, full_history)
    retrieval_query = _build_retrieval_query(effective_query, history)
    question_mode = _question_mode(effective_query)
    cross_document = question_mode == "comparison" and _cross_document_comparison(effective_query)
    if cross_document:
        documents = _select_broad_chunks(
            pdf_index.chunks, MAX_COMPARISON_CHUNKS
        )
    else:
        documents = pdf_index.retrieve(
            retrieval_query,
            broad=question_mode == "synthesis",
        )
    if not documents:
        return RagAnswer(
            text="I don't know based on the provided documents.", pages=(), sources=()
        )

    context = "\n\n".join(_format_document(doc) for doc in documents)
    payload = {
            "context": context,
            "history": history_text or "(none)",
            "task_guidance": _task_guidance(question_mode, is_retry=is_retry) if question_mode != "comparison" or cross_document else (
                "Compare only the concepts requested, using the relevant excerpts. "
                "Explain shared properties and differences with exact citations. "
                "Do not summarize unrelated PDFs. Respect the requested length."
            ),
            "question": effective_query,
        }
    chain = _answer_chain()
    response = _generate(chain, payload, on_update)
    text, reason, usage = response_details(response)
    attempts = 1
    # Retry only a token-limit/empty response, never a safety-blocked response.
    if reason == "MAX_TOKENS" or (not text and reason in {"STOP", "UNKNOWN"}):
        attempts = 2
        payload["task_guidance"] += (
            " Return a complete but shorter answer, at most 500 words."
        )
        response = _generate(chain, payload, on_update)
        text, reason, second_usage = response_details(response)
        usage = {"first_attempt": usage, "second_attempt": second_usage}
    if not text:
        raise RuntimeError(f"The model returned no answer (finish reason: {reason}). Retry the question.")
    warning = ""
    if reason not in {"STOP", "UNKNOWN"}:
        warning = f"The answer may be incomplete. Model finish reason: {reason}."
    citation_warning = _citation_warning(text, documents)
    warning = " ".join(part for part in (warning, citation_warning) if part)
    pages = tuple(
        sorted(
            {
                int(doc.metadata["page"]) + 1
                for doc in documents
                if isinstance(doc.metadata.get("page"), int)
            }
        )
    )
    sources = _source_labels(documents)
    evidence = tuple({
        "source": str(doc.metadata.get("source", "Unknown PDF")),
        "page": doc.metadata.get("page", -1) + 1,
        "text": doc.page_content,
    } for doc in documents)
    return RagAnswer(text=text, pages=pages, sources=sources,
                     finish_reason=reason, usage=usage, warning=warning,
                     attempts=attempts, evidence=evidence)


def _generate(chain, payload, on_update):
    """Stream complete text snapshots while retaining finish/usage metadata.

    An empty snapshot resets the display before each attempt. Exceptions are
    propagated: a broken stream must never be saved as a successful answer.
    """
    if on_update is None:
        return chain.invoke(payload)
    on_update("")
    response = None
    for chunk in chain.stream(payload):
        response = chunk if response is None else response + chunk
        text, _, _ = response_details(response)
        on_update(text)
    return response if response is not None else ""


def _cross_document_comparison(query: str) -> bool:
    return bool(re.search(r"\b(pdfs?|documents?|chapters?|files?)\b", query, re.I))


def _citation_warning(text: str, documents: Sequence[Document]) -> str:
    """Validate marker membership only; this is NOT claim entailment checking."""
    valid = {_format_document(doc).split("\n", 1)[0] for doc in documents}
    cited = re.findall(r"\[[^\[\]\n]+,\s*Pages?\b[^\[\]\n]*\]", text, re.I)
    if any(marker not in valid for marker in cited):
        return "Some citations do not match the retrieved source markers. Verify claims against the source excerpts."
    if not cited and "i don't know based on the provided documents" not in text.casefold():
        return "No source citations were provided. Verify claims against the retrieved excerpts."
    return ""


def get_answer(
    query: str,
    retriever: PdfIndex,
    chat_history: Sequence[dict[str, str]] | None = None,
) -> str:
    """Backward-compatible helper that returns only the generated text."""
    return answer_question(query, retriever, chat_history).text


def _format_document(document: Document) -> str:
    page = document.metadata.get("page")
    source = os.path.basename(str(document.metadata.get("source", "Unknown PDF")))
    marker = (
        f"[{source}, Page {page + 1}]"
        if isinstance(page, int)
        else f"[{source}, Page unknown]"
    )
    return f"{marker}\n{document.page_content}"


def _source_labels(documents: Sequence[Document]) -> tuple[str, ...]:
    """Group retrieved pages by PDF to keep the source footer readable."""
    pages_by_source: dict[str, set[int]] = {}
    for document in documents:
        source = os.path.basename(
            str(document.metadata.get("source", "Unknown PDF"))
        )
        pages = pages_by_source.setdefault(source, set())
        page = document.metadata.get("page")
        if isinstance(page, int):
            pages.add(page + 1)

    labels = []
    for source in sorted(pages_by_source):
        pages = sorted(pages_by_source[source])
        page_text = _format_page_ranges(pages)
        labels.append(f"{source}, pages {page_text}" if page_text else source)
    return tuple(labels)


def _format_page_ranges(pages: Sequence[int]) -> str:
    if not pages:
        return ""
    ranges = []
    start = previous = pages[0]
    for page in pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


def _task_guidance(question_mode: str, *, is_retry: bool = False) -> str:
    retry_guidance = (
        " A previous response was incomplete. Regenerate the complete answer "
        "from the beginning; do not merely continue the broken response."
        if is_retry
        else ""
    )
    if question_mode == "comparison":
        guidance = (
            "This is a cross-document comparison. Compare the PDFs even when "
            "they cover different subjects; different scope is itself an important "
            "difference, not a reason to say the answer is unknown. Use a separate "
            "short heading for every PDF and describe its focus, key ideas, and "
            "distinctive details with bullet points. Do not use a Markdown table. "
            "Then add sections for genuine shared ideas, important differences, "
            "and how the documents relate. Do not claim a similarity unless the "
            "context supports it. Cite every document section and major comparison "
            "with filename-and-page markers."
            " If the question names a subset of PDFs, discuss only that subset."
            " Respect any requested word limit."
        )
        return guidance + retry_guidance
    if question_mode == "synthesis":
        guidance = (
            "This is a synthesis request. The supplied excerpts are the material "
            "to summarize or compare; an explicit summary sentence does not need "
            "to exist in the documents. Synthesize the available content instead "
            "of replying that the answer is unknown. For a whole-collection request, "
            "cover each PDF represented in the context, then give combined themes, "
            "differences, or takeaways as appropriate. For a specific chapter or "
            "document request, summarize only the requested material. Respect "
            "requested word and bullet limits."
        )
        return guidance + retry_guidance
    guidance = (
        "Answer the specific question from the most relevant supplied excerpts. "
        "Say the answer is unknown only when those excerpts truly lack it."
    )
    return guidance + retry_guidance


def _format_history(messages: Sequence[dict[str, str]]) -> str:
    lines = []
    for message in messages:
        role = "User" if message.get("role") == "user" else "Assistant"
        content = message.get("content", "").strip()[:1500]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_retrieval_query(
    query: str, messages: Sequence[dict[str, str]]
) -> str:
    """Keep follow-up context useful without embedding the whole conversation."""
    recent_questions = [
        message.get("content", "").strip()[:500]
        for message in messages
        if message.get("role") == "user" and message.get("content", "").strip()
    ][-2:]
    if not recent_questions:
        return query
    return "Previous questions: " + " | ".join(recent_questions) + f"\nCurrent question: {query}"


def _resolve_question(
    query: str, messages: Sequence[dict[str, str]]
) -> tuple[str, bool]:
    """Map short retry/continue messages back to the last substantive question."""
    if not _is_retry_message(query):
        return query, False

    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        previous = message.get("content", "").strip()
        if previous and not _is_retry_message(previous):
            return previous, True
    return query, False


def _is_retry_message(query: str) -> bool:
    normalized = " ".join(query.casefold().split()).strip(".!?")
    retry_phrases = {
        "continue",
        "continue the answer",
        "complete the answer",
        "finish the answer",
        "it stopped",
        "it was cut off",
        "where is the output",
        "where is the answer",
        "no output",
        "retry",
        "try again",
        "regenerate",
        "regenerate the answer",
    }
    return normalized in retry_phrases
def _question_mode(query: str) -> str:
    normalized = query.casefold()
    if "compar" in normalized or "difference between" in normalized:
        return "comparison"
    phrases = (
        "summarize",
        "summary",
        "main topic",
        "key takeaway",
        "overview",
        "entire document",
        "whole document",
        "all document",
        "across the document",
        "each uploaded pdf",
    )
    return "synthesis" if any(phrase in normalized for phrase in phrases) else "specific"


def _is_broad_document_question(query: str) -> bool:
    """Backward-compatible predicate used by tests and external callers."""
    return _question_mode(query) != "specific"
