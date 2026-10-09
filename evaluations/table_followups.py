"""Live regression for the two table requests reported from Cloud.

Uses the original local networking PDFs and consumes Gemini generation quota.
Answers and evidence are saved privately, never committed.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import time

from src.pdf_rag.ingestion import process_pdfs
from src.pdf_rag.pipeline import answer_question


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=("comparison", "summary", "first"), default="comparison")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path; existing reports are preserved")
    files = sorted(args.pdf_dir.glob("CHAPTER*.pdf"))
    if len(files) != 3:
        parser.error("Expected three CHAPTER PDFs")
    index = process_pdfs([(str(path), path.name) for path in files])
    history = [{"role": "user", "content": "Compare the uploaded PDFs, explaining their shared ideas and important differences."}]
    if args.scenario == "summary":
        history = [{"role": "user", "content": "Provide a detailed summary of each uploaded PDF, followed by a combined overview."},
                   {"role": "assistant", "content": "I don't know based on the provided documents."}]
    elif args.scenario == "first":
        history = []
    results = []
    try:
        for query in ("make difference table", "make differnce table of 3 chapters"):
            started = time.perf_counter()
            answer = answer_question(query, index, history, on_update=lambda text: None)
            lines = [line for line in answer.text.splitlines() if line.strip().startswith("|")]
            populated_rows = [line for line in lines if not re.fullmatch(r"[|:\-\s]+", line)]
            result = {"question": query, "seconds": time.perf_counter() - started,
                      "table_lines": len(lines), "populated_rows_including_header": len(populated_rows),
                      **asdict(answer)}
            results.append(result)
            print(query, answer.finish_reason, f"{result['seconds']:.2f}s", f"table lines={len(lines)}", f"warnings={answer.warning!r}", flush=True)
            history.extend([{"role": "user", "content": query}, {"role": "assistant", "content": answer.text}])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        index.close()


if __name__ == "__main__":
    main()
