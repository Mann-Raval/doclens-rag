"""Opt-in operational logs; never log prompts, document names, or text."""
import json
import os
from pathlib import Path


def log_metrics(event: str, **values):
    if os.getenv("DOCLENS_METRICS", "0") != "1":
        return
    # Linux process RSS snapshot, not per-user memory or peak memory.
    try:
        resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
        values["process_rss_mb"] = round(resident_pages * os.sysconf("SC_PAGE_SIZE") / 1024**2, 2)
    except (OSError, ValueError, AttributeError, IndexError):
        values["process_rss_mb"] = None
    print(json.dumps({"event": event, **values}), flush=True)
