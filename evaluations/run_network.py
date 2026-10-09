"""Run authorized live Gemini evaluation; save private answers/evidence locally.

Usage: python -m evaluations.run_network --pdf-dir PATH [--limit 30]
Each case is independent except explicit follow-up history. No automatic
entailment score is claimed. Review the saved answers against their evidence.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from datetime import datetime, timezone

from .network_cases import CASES, FOLLOW_UP_HISTORY
from src.pdf_rag.ingestion import process_pdfs
from src.pdf_rag.pipeline import answer_question
from src.pdf_rag.config import DEFAULT_CHAT_MODEL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--start", type=int, default=1, help="First one-based case ID; use a separate output file when resuming")
    parser.add_argument("--cases", type=int, nargs="+", choices=range(1, 31), help="Only run selected case IDs")
    parser.add_argument("--output", type=Path, default=Path("evaluations/local-results/network.json"))
    args = parser.parse_args()
    if not 1 <= args.start <= 30 or not 1 <= args.limit <= 30:
        parser.error("--start and --limit must be between 1 and 30")
    if args.output.exists():
        parser.error("Output already exists; choose a new --output to preserve previous results")
    files = sorted(args.pdf_dir.glob("CHAPTER*.pdf"))
    if len(files) != 3:
        parser.error("Expected the three CHAPTER PDFs in --pdf-dir")
    report = {"model": os.getenv("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL),
              "started_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "code_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("src/pdf_rag").glob("*.py")},
              "documents": [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
              "results": []}
    start = time.perf_counter()
    index = process_pdfs([(str(p), p.name) for p in files])
    report["index_seconds"] = time.perf_counter() - start
    report["chunks"] = len(index.chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Indexed {len(index.chunks)} chunks in {report['index_seconds']:.2f}s", flush=True)
    try:
        for number, (task, question, expected) in enumerate(CASES[:args.limit], 1):
            if number < args.start:
                continue
            if args.cases and number not in args.cases:
                continue
            history = []
            if number in FOLLOW_UP_HISTORY:
                history = [{"role": "user", "content": FOLLOW_UP_HISTORY[number]}]
            row = {"id": number, "task": task, "question": question, "history": history,
                   "review_criteria": expected, "review": "pending"}
            start = time.perf_counter()
            first_text = []
            def update(text):
                if text and not first_text:
                    first_text.append(time.perf_counter() - start)
            try:
                answer = answer_question(question, index, history, on_update=update)
                row.update(asdict(answer))
                row["first_text_seconds"] = first_text[0] if first_text else None
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
            row["seconds"] = time.perf_counter() - start
            report["results"].append(row)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"{number:02d} {task}: {row['seconds']:.2f}s {row.get('finish_reason', 'ERROR')}", flush=True)
            if "error" in row:
                print("Stopped after provider failure; inspect local report before retrying.", flush=True)
                break
    finally:
        index.close()


if __name__ == "__main__":
    main()
