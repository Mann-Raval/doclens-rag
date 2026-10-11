# Stable comparison follow-ups — build 1.3.11

The reported regression was a Chapter 2 focus present in prose disappearing in
its table follow-up. The follow-up previously regenerated each source profile.

The pipeline now retains structured comparison cells with the answer and reuses
them for formatting-only requests. Evidence order and citation mappings remain
unchanged. The follow-up requires zero model calls and zero retrieval calls.
Missing cells now say a summary is unavailable, not that evidence is absent.

Automated checks cover exact text/citation preservation, repeated formatting,
stream callback output, different/replaced index rejection, cleared history,
new topic and retry behaviour, intervening answers, and Streamlit metadata storage
and clear-chat cleanup. All 74 tests passed on 2026-10-11 (6.309 seconds);
`git diff --check` also passed. The suite required permission to create temporary
PDFs outside the workspace; the initial sandboxed run hit a filesystem denial.

This change does not improve or certify the original answer's semantic support.
No live-provider evaluation was necessary for the deterministic rendering change.
Cloud verification remains pending: start a new comparison on build 1.3.11, then
ask `make difference table` and check that its cells match the preceding answer.
No release tag or merge is implied by this regression fix.
