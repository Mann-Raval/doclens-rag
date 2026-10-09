"""Replay deterministic citation rendering against saved evidence; no API calls.

This checks reference membership, NOT whether claims are supported. Keep output
inside ignored local-results because reports contain private source excerpts.
"""
import argparse
import hashlib
import json
from pathlib import Path

from langchain_core.documents import Document
from src.pdf_rag.pipeline import _render_evidence_ids, _normalize_citations, _citation_warning


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new filename")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    report["citation_replay"] = {
        "input_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
        "pipeline_sha256": hashlib.sha256(Path("src/pdf_rag/pipeline.py").read_bytes()).hexdigest(),
        "new_model_calls": 0,
        "scope": "Formatting/reference membership only, not claim entailment or fresh generation",
    }
    for row in report["results"]:
        if "text" not in row:
            continue
        documents = [Document(page_content=e["text"], metadata={"source": e["source"], "page": e["page"] - 1})
                     for e in row["evidence"]]
        row["original_text"] = row["text"]
        row["text"] = _normalize_citations(_render_evidence_ids(row["text"], documents), documents)
        row["citation_warning_after_replay"] = _citation_warning(row["text"], documents)
        print(f"Case {row['id']:02d}: {row['citation_warning_after_replay'] or 'reference membership OK'}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
