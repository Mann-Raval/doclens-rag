# Stage 1 release checks — 2026-10-10

Status: tested demo, NOT approved for v1.0. Build 1.3.7 fixes citation formatting;
cross-document claim attribution remains a known quality blocker.

## Completed

- 59 offline regression tests pass, including reference groups/ranges,
  initialization, session collections, upload limits, retries and table routing.
- Fresh 30-question networking evaluation completed: 30 STOP responses, no
  citation-membership warnings, all four missing-information cases abstained.
  Median response 2.58 s; nearest-rank p95 6.52 s. These are local timings.
- OS notes live regression: 295 indexed passages, 33 comparison passages supplied.
  Inventory completed in 4.86 s; table follow-up in 4.37 s with 25 table lines.
  No unknown-citation warning; heuristic coverage warning correctly remains.
  This checks completion/format/reference membership, not exhaustive coverage.
- User tested normal and incognito sessions with different PDFs and asked about
  the other session's content. Both abstained. Manual isolation check passed;
  this is not a penetration test or a concurrent load benchmark.

## Cloud observations supplied by the user

Deployment: https://doclens-rag.streamlit.app/ (screenshots show build 1.3.6).
Python 3.12.15, Streamlit 1.65.0, Chroma 1.5.9.

For the 290-page OS notes, 295 passages, 9,809,646 upload bytes:

| Stage | Seconds | Process RSS snapshot (MB) |
| --- | ---: | ---: |
| Validation, completed upload | 0.187 | 272.68 |
| Extraction | 8.088 | 266.32 |
| Chunking | 0.012 | 266.32 |
| Embedding/indexing | 11.487 | 943.22 |
| Overall indexing | 19.786 | 943.22 |

The log includes a first-use model download. A later incognito screenshot shows
16.3 s indexing; a different, eight-passage PDF shows 0.5 s. These are different
runs/documents, not a controlled speed comparison. Three answer logs show
3.470, 1.200 and 5.452 s total, with first text at 1.042, 0.905 and 2.745 s.
RSS is process-wide, not peak or per-session memory. These samples do not establish
capacity or reliable Cloud p95 latency. Installation logs were not committed.

## Citation warning resolved

The user pasted an explicit `[S1-S33]` range. All 33 IDs existed in the retrieved
context, but the previous renderer accepted only single/comma-separated IDs.
The new renderer accepts valid ranges, semicolon groups and whitespace. Unknown
or reversed ranges remain visible and flagged; plain numeric lists are not
guessed to be citations. Reference membership does not establish claim support.

## Failed quality gate and rejected experiment

The 30-case run still contained an unsupported chapter-1 checksum attribution
to page 53, whose supplied excerpt discusses LAN drawbacks and IPv4 addressing.
A bounded second LLM review was experimentally added and tested on cases
13, 19, 25 and 26. All completed, but case 25 still claimed both chapters use
checksums while citing only chapter-2 pages 7 and 28. Case 13 also generalized
reliable transport language across TCP/UDP. The review added latency (5.12–10.03 s
for these answers) without reliably resolving the blocker, so it was removed
from the shipped code. The private report preserves the experiment.

## Remaining release gates

1. Resolve cross-document claim attribution with source-scoped generation and
   explicit claim/evidence validation; rerun and review affected answers.
2. Review factual support/completeness beyond citation membership, including OS
   comparison claims. No overall accuracy percentage is currently justified.
3. Check final build on Cloud, including replacement/removal/retry and resource
   behavior with simultaneous uploads. Current memory snapshots warrant caution.
4. Only after the gates pass: merge the tested branch and publish v1.0.

No merge, release tag or GitHub release was created. Private answer/evidence
reports remain ignored under `evaluations/local-results/`; source PDFs and API
keys are not published.
