# Stage 1 validation — 2026-10-09

Historical first run. See [the subsequent retest](stage1-retest.md) for the
completed 30-question runs and correction of the UDP-field assessment below.

**Release decision: HOLD.** Streaming and offline regressions pass. Live
answer-quality validation is incomplete, and no Cloud deployment has been tested.

## Environment and scope

- Local Windows / Python 3.12 virtual environment, feature branch
  `feat/basic-rag-foundation`.
- Gemini `gemini-2.5-flash-lite`, local ONNX MiniLM, ephemeral Chroma.
- Three user-provided networking chapters: introduction (59 pages), data link
  and network (38 pages), transport/application (26 pages); 184 indexed chunks.
- PDFs and the private report (including source excerpts) are not committed.
- The live run used streaming but preceded the citation-prompt and focused
  comparison fixes described below. These numbers are not a post-fix benchmark.

## What actually ran

| Check | Result |
| --- | --- |
| Offline component/UI tests after changes | 26 passed |
| Real-PDF extraction and MiniLM/Chroma indexing | Passed |
| Planned live question set | 30 cases |
| Completed live answers | 21, all STOP, one attempt each |
| Case 22 | Gemini daily generation quota failure (429) |
| Cases 23–30 | Not executed |
| Post-fix live retest | Pending quota availability |
| Deployed browser sessions / resource measurements | Not executed |

The API reported `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20,
with approximately 12.5 hours until retry. The report contains 21 successful
responses before the failure; this does not imply any guaranteed quota capacity.
Local embedding does not remove the separate Gemini generation quota.

## Local timings (completed answers only)

| Metric | Value |
| --- | --- |
| Indexing, model already cached | 8.37 s |
| Time to first nonempty text, median / p95 | 2.14 / 3.09 s |
| Total answer latency, median / p95 | 3.89 / 13.78 s |

p95 uses the nearest-rank method over 21 completed requests. These are a single
local sequential run, not Cloud timings or a concurrency benchmark. The failed
request is excluded. Process memory was not measured in this run.

## Answer and citation findings

Manual spot review compared selected answers to the retrieved text. This is not
a complete claim-by-claim audit or a model-quality percentage.

| Cases | Finding | Action / status |
| --- | --- | --- |
| 1, 4 | Copied fictional `guide.pdf` citations from the prompt example | Removed that example; added marker-membership warnings; live retest pending |
| 2 | Correct UDP size but silently omitted requested header fields | Extracted page text lacks the diagram's full field list; prompt now requires explicit partial-answer limitations |
| 3, 5, 6, 9, 11, 12 | Spot-checked handshake, Stop-and-Wait, VLAN and HTTPS claims against retrieved evidence | Supporting excerpts present; not a general accuracy claim |
| 8, 13, 14, 16–18 | Combined multiple pages inside one noncanonical citation marker | Prompt now requests separate exact markers; validator flags mismatches rather than guessing replacements |
| 10 | Abstained on UDP fields absent from extracted text | Appropriate limitation for text-only ingestion; not proof that the original PDF lacks the information |
| 13, 19 | Original whole-document comparison/retry produced full prose, covering all three PDFs | Truncation symptom not reproduced in this run; citation quality still fails (case 19 omitted inline citations entirely) |
| 20 | TCP comparison described a three-way handshake for termination too | Needs conflict-aware grounding review against detailed chapter text; not accepted as a clean pass |
| 21 | HTTP/HTTPS question expanded into unrelated summaries of every PDF | Topic comparisons now use semantic search and focused guidance; live retest pending |

Marker validity checks only whether a reference exists among retrieved passages.
It does **not** prove that a cited passage supports the adjacent claim. Source
notes can also contain oversimplifications or conflicting statements. Do not
describe this report as 21 correct answers or a completed 30-question evaluation.

## Offline lifecycle coverage

Streamlit AppTest uses controlled indexing/generation to exercise same-upload
reuse, same-name changed-content replacement, removal, failed replacement,
explicit retry after failure, and separate chat/index state in two sessions.
A separate real-Chroma test checks collection isolation and deletion. Streaming
tests cover text/metadata aggregation, replacement on truncation retry, and
propagating interruptions without silently saving partial success.

These are not concurrent real-browser or deployed-host tests. Removal clears
old error state as well as chat/index state. Opt-in operational logging now
supports Cloud timing and Linux process RSS snapshots without logging content.

## Required before v1.0

1. After quota reset, run cases 22–30 with a fresh output file; then retest all
   30 on the final code, budgeting across days if needed. Do not bypass quota.
2. Review completeness and claim-level support for every answer, especially
   comparisons, partial evidence, contradictory notes, and missing information.
3. Deploy the candidate branch through the owner's Streamlit account; record
   its URL/commit and follow `docs/deployment.md` for browser and resource checks.
4. Fix remaining failures, rerun checks, then merge and publish `v1.0`.

No merge, release tag, or GitHub release was created during this validation.
