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
from .comparisons import is_comparison_inventory, comparison_passages
from .source_comparison import compare_sources, requested_source_chunks

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
    inventory = is_comparison_inventory(effective_query)
    cross_document = question_mode == "comparison" and _cross_document_comparison(effective_query)
    if inventory:
        documents = comparison_passages(pdf_index.chunks)
    elif cross_document:
        documents = _select_broad_chunks(
            requested_source_chunks(pdf_index.chunks, effective_query), MAX_COMPARISON_CHUNKS
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

    context = "\n\n".join(f"Evidence [S{i}]\n{_format_document(doc)}" for i, doc in enumerate(documents, 1))
    payload = {
            "context": context,
            "history": history_text or "(none)",
            "task_guidance": _task_guidance(question_mode, is_retry=is_retry) if question_mode != "comparison" or cross_document else (
                "Compare only the concepts requested, using the relevant excerpts. "
                "Explain shared properties and differences with evidence-ID citations. "
                "Do not summarize unrelated PDFs. Respect the requested length."
            ),
            "question": effective_query,
        }
    limit_match = re.search(r"\b(?:at most|no more than|under|within|in)\s+(\d+)\s+words\b", effective_query, re.I)
    word_limit = int(limit_match.group(1)) if limit_match else None
    if word_limit:
        payload["task_guidance"] = (
            f"Answer the requested task in at most {word_limit} words of prose. "
            "This word limit overrides all default detailed-answer templates. "
            "Use compact paragraphs or bullets, no nested headings. For comparisons, "
            "briefly cover each requested document plus supported shared ideas and "
            "differences. Cite evidence IDs. Do not list incidental technical details."
        )
    if _requests_table(effective_query):
        # The subject has already been resolved from user turns. Do not let an
        # earlier failed assistant answer become a template or evidence.
        payload["history"] = _format_history([message for message in history if message.get("role") == "user"]) or "(none)"
        payload["task_guidance"] = payload["task_guidance"].replace("Do not use a Markdown table.", "")
        payload["task_guidance"] += (
            " The user's table request overrides the heading-and-bullet template. "
            "Return a COMPLETE Markdown comparison table with a header, separator "
            "row, and populated rows, not just an introduction. Use short cells, "
            "plain text and semicolons within cells; never insert HTML or <br> tags. "
            "Use concise, directly relevant citations rather than listing every "
            "retrieved excerpt. Name any citation column 'Sources', not 'Evidence IDs'. "
            "cover all requested documents or concepts, and cite evidence IDs in "
            "the relevant cells. For documents, compare their focus, scope, and "
            "important differences. Synthesize the table from the excerpts; the "
            "PDFs do not need to contain an existing comparison table. Do not "
            "switch to comparing incidental topics "
            "such as HTTP/HTTPS unless those were requested. Use only the supplied "
            "excerpts as evidence, not previous assistant answers."
        )
    if inventory:
        payload["history"] = "(Use the current evidence, not previous assistant answers.)"
        payload["task_guidance"] = (
            "Build an exam-revision inventory of distinct concept comparisons WITHIN the notes, "
            "not a comparison of PDF files. Identify supported pairs or groups throughout the "
            "supplied excerpts, deduplicate repeated comparisons, and cover each supported pair. "
            "Do not focus on only the first pair. For each pair give concise, contrasting facts "
            "with evidence-ID citations. Use a separate compact Markdown table for each pair "
            "if tables were requested; otherwise use short sections. No HTML or <br> tags. "
            "Do not invent pairs or fill missing differences from general knowledge. "
            "Start with a list of the comparison topics you found. This is a heuristic scan "
            "with bounded excerpts: never claim these are ALL comparisons in the full PDF "
            "or that the PDF contains no others. State the coverage limitation briefly."
        )
        if word_limit:
            payload["task_guidance"] += f" Keep the response within {word_limit} words."
    chain = _answer_chain()
    stream_update = (lambda text: on_update(_render_evidence_ids(text, documents))) if on_update else None
    scoped_comparison = cross_document and not inventory and len({doc.metadata.get("source") for doc in documents}) > 1
    comparison_warning = ""
    if scoped_comparison:
        text, usage, comparison_warning, attempts = compare_sources(
            chain, documents, payload, table=_requests_table(effective_query),
            word_limit=word_limit, on_update=stream_update,
        )
        reason = "STOP"
    else:
        response = _generate(chain, payload, stream_update)
        text, reason, usage = response_details(response)
        attempts = 1
    # Retry only a token-limit/empty response, never a safety-blocked response.
    too_long = word_limit and _prose_word_count(text) > word_limit
    if not scoped_comparison and (reason == "MAX_TOKENS" or (reason in {"STOP", "UNKNOWN"} and (not text or too_long))):
        attempts = 2
        payload["task_guidance"] += (
            f" Return a complete but shorter answer, at most {word_limit or 500} words."
        )
        response = _generate(chain, payload, stream_update)
        text, reason, second_usage = response_details(response)
        usage = {"first_attempt": usage, "second_attempt": second_usage}
    if not text:
        raise RuntimeError(f"The model returned no answer (finish reason: {reason}). Retry the question.")
    warning = comparison_warning
    if reason not in {"STOP", "UNKNOWN"}:
        warning = f"The answer may be incomplete. Model finish reason: {reason}."
    text = _render_evidence_ids(text, documents)
    text = _normalize_citations(text, documents)
    citation_warning = _citation_warning(text, documents)
    warning = " ".join(part for part in (warning, citation_warning) if part)
    if inventory:
        warning = (warning + f" Comparison discovery scanned {len(pdf_index.chunks)} passages and supplied "
                   f"{len(documents)} to the model. Comparisons without explicit textual cues, including "
                   "image-only tables, may be missed; this is not a verified exhaustive list.").strip()
    if word_limit and _prose_word_count(text) > word_limit:
        warning = (warning + f" The answer exceeds the requested {word_limit}-word limit.").strip()
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


def _prose_word_count(text: str) -> int:
    return len(re.sub(r"\[[^\]\n]*\]", "", text).split())


def _cross_document_comparison(query: str) -> bool:
    query = _normalized_question(query)
    if "requested format:" in query:
        subject, formatting = query.split("requested format:", 1)
        collection_scope = re.search(r"\b(?:all|each|uploaded)\b[^.?!]*\b(?:pdfs?|documents?|chapters?)\b|\bcollection\b", subject)
        if _requests_table(formatting) and _question_mode(subject) == "synthesis" and collection_scope:
            return True
    # "Compare TCP and UDP using these PDFs" is a topic comparison.
    qualifiers = r"(?:(?:all|the|these|those|both|uploaded|selected|three|two|\d+)\s+)*"
    objects = r"(?:pdfs?|documents?|chapters?|files?)\b"
    return bool(re.search(r"\b(?:compar\w*\s+|differences?\s+between\s+)" + qualifiers + objects, query, re.I)
                or re.search(r"\bhow\s+do\s+" + qualifiers + objects + r".*\bdiffer\b", query, re.I)
                or re.search(r"\btable\s+(?:of|for|between|comparing)\s+" + qualifiers + objects, query, re.I))


def _render_evidence_ids(text: str, documents: Sequence[Document]) -> str:
    """Expand known IDs deterministically; retain unknown IDs for warnings."""
    markers = {str(i): _format_document(doc).split("\n", 1)[0] for i, doc in enumerate(documents, 1)}
    def render(match):
        ids = []
        for group in re.split(r"\s*[,;]\s*", match.group(1)):
            bounds = re.findall(r"S(\d+)", group)
            if len(bounds) == 2:
                first, last = map(int, bounds)
                if not 1 <= first <= last <= len(documents):
                    return match.group(0)
                ids.extend(str(i) for i in range(first, last + 1))
            else:
                ids.extend(bounds)
        if not all(identity in markers for identity in ids):
            return match.group(0)
        return " ".join(dict.fromkeys(markers[identity] for identity in ids))
    identity = r"S\d+(?:\s*[-–]\s*S\d+)?"
    return re.sub(r"\[\s*(" + identity + r"(?:\s*[,;]\s*" + identity + r")*)\s*\]", render, text)


def _citation_warning(text: str, documents: Sequence[Document]) -> str:
    """Validate marker membership only; this is NOT claim entailment checking."""
    if re.search(r"\[\s*S\d+[^\]\n]*\]", text):
        return "Some evidence IDs are unknown. Verify claims against the retrieved source excerpts."
    valid = {_format_document(doc).split("\n", 1)[0] for doc in documents}
    cited = re.findall(r"\[[^\[\]\n]+,\s*Pages?\b[^\[\]\n]*\]", text, re.I)
    if any(marker not in valid for marker in cited):
        return "Some citations do not match the retrieved source markers. Verify claims against the source excerpts."
    if not cited and "i don't know based on the provided documents" not in text.casefold():
        return "No source citations were provided. Verify claims against the retrieved excerpts."
    return ""


def _normalize_citations(text: str, documents: Sequence[Document]) -> str:
    """Expand explicit page lists only when every referenced page was retrieved.

    This repairs formatting, not attribution: never infer a filename/page,
    substitute evidence, or imply claim support merely from a valid marker.
    """
    valid = {_format_document(doc).split("\n", 1)[0] for doc in documents}
    def expand(match):
        source, pages = match.groups()
        markers = [f"[{source}, Page {page}]" for page in re.findall(r"\d+", pages)]
        return " ".join(markers) if all(marker in valid for marker in markers) else match.group(0)
    return re.sub(r"\[([^\[\]\n]+?), Page (\d+(?:,\s*(?:Page\s+)?\d+)+)\]", expand, text)


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
            "with evidence-ID citations."
            " Keep the comparison focused on scope and major concepts rather than "
            "incidental commands, numbers, or exhaustive topic inventories. A shared "
            "mechanism must be explicitly supported for EACH document you attribute "
            "it to; a shared goal does not establish a shared mechanism. Name the "
            "specific documents that share a property instead of saying 'all' loosely."
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
            " Preserve distinctions between categories: do not combine differently "
            "classified protocols or mechanisms into a single class. Keep each "
            "bullet focused, and check that every attributed property is explicitly "
            "supported by its own cited excerpt."
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
    if _is_format_followup(query):
        for message in reversed(messages):
            previous = message.get("content", "").strip()
            if message.get("role") == "user" and previous and not _is_retry_message(previous) and not _is_format_followup(previous):
                return f"{previous}\nRequested format: {query}", False
        if is_comparison_inventory(query):
            return query, False
        return f"Compare the uploaded PDFs.\nRequested format: {query}", False
    if not _is_retry_message(query):
        return query, False

    for position in range(len(messages) - 1, -1, -1):
        message = messages[position]
        if message.get("role") != "user":
            continue
        previous = message.get("content", "").strip()
        if previous and not _is_retry_message(previous):
            resolved, _ = _resolve_question(previous, messages[:position])
            return resolved, True
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
def _normalized_question(query: str) -> str:
    normalized = " ".join(query.casefold().split())
    return re.sub(r"\bdiffernce\b", "difference", normalized)


def _is_format_followup(query: str) -> bool:
    normalized = _normalized_question(query).strip(".!? ")
    if re.fullmatch(r"(?:all |the )?(?:differences?|comparisons?) in (?:a )?table(?: form)?", normalized):
        return True
    return bool(re.fullmatch(
        r"(?:please )?(?:(?:make|create|show|give)(?: me)? (?:a |the )?(?:(?:difference|comparison) )?table|"
        r"(?:put|present|format|convert|turn) (?:it|this|that|the answer|the comparison) (?:in|into|as) (?:a )?table)"
        r"(?: please)?", normalized))


def _requests_table(query: str) -> bool:
    normalized = _normalized_question(query)
    return bool(re.search(r"\b(?:make|create|show|give|format|convert|present|put|turn)\b.*\btable\b|"
                          r"\b(?:in|as)\s+(?:a\s+)?table\b|\b(?:comparison|difference)\s+tables?\b", normalized))


def _question_mode(query: str) -> str:
    normalized = _normalized_question(query)
    if "compar" in normalized or "difference" in normalized or (_requests_table(query) and _cross_document_comparison(query)):
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
