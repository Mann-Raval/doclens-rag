# Missing comparison cells — build 1.3.14

The Cloud screenshot showed two Chapter 2 cells missing on the initial answer,
then present after a manual full-answer retry. The pipeline now makes at most one
automatic targeted repair call per incomplete source, after deterministic cell
validation. This replaces neither successful draft cells nor their evidence IDs.

Repair uses the same isolated source context and only the missing feature labels.
The same schema, word bounds and citation-ownership checks apply. Invalid repairs
and provider failures retain the draft and surface an unresolved-feature warning.
Safety-blocked initial responses are not retried; a blocked optional repair is
discarded, with a failure warning and no further retry. Private provider error
bodies are not displayed by the repair handler.

All 80 automated tests passed (6.409 seconds). Regression coverage includes:

- No repair call for complete profiles.
- Invalid IDs produce missing cells eligible for repair.
- Repair fills only missing labels and cannot overwrite accepted cells.
- Identical source-only context on draft and repair.
- Invalid JSON, empty repairs, connection failure and safety block stop after
  one repair, retain valid cells, and do not leak private error details.
- Existing table reformatting preserves the final snapshot without model calls.

Limits: an incomplete source can add one model call and corresponding latency.
Missing evidence must not be invented to fill a table. Reference membership is
still not semantic support; the citation audit's release blockers remain.

Live check: network case 25 indexed 184 chunks in 11.79 seconds and generated
all eight cells in 5.08 seconds, STOP, with two draft calls and no repair needed.
This confirms the unchanged complete-answer path, not live recovery frequency.
The private report is `evaluations/local-results/network-cell-repair-1314.json`.
The answer still mentioned distance-vector routing without clear support in its
cited excerpts, so it is not a semantic accuracy pass. Missing-cell repair is
verified by controlled tests that deliberately omit/reject cells.
