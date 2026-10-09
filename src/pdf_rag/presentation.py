"""Display-only cleanup; original answers and evidence remain unchanged."""
import re

MARKER = r"\[[^\[\]\n]+, Page \d+\]"
CLUSTER = re.compile(MARKER + r"(?:[ ,\t]*" + MARKER + r")*")
BREAK = re.compile(r"(?:<br\s*/?>|&lt;br\s*/?&gt;)[ \t]*(?:[•·][ \t]*)?", re.I)


def present_answer(text: str) -> tuple[str, list[str]]:
    """Use answer-local numbered references and safe plain-text table cells.

    A reference number is only a label, not a support/entailment verdict.
    No HTML rendering is enabled. Fenced code blocks are preserved verbatim.
    """
    references = []
    numbers = {}

    def compact(match):
        ids = []
        for marker in re.findall(MARKER, match.group(0)):
            if marker not in numbers:
                references.append(marker)
                numbers[marker] = len(references)
            number = numbers[marker]
            if number not in ids:
                ids.append(number)
        return "[" + ", ".join(map(str, ids)) + "]"

    parts = re.split(r"(```[\s\S]*?```)", text)
    for position in range(0, len(parts), 2):
        cleaned = []
        for line in parts[position].split("\n"):
            line = BREAK.sub("; " if line.lstrip().startswith("|") else "\n\n", line)
            cleaned.append(CLUSTER.sub(compact, line))
        parts[position] = "\n".join(cleaned)
    return "".join(parts), references
