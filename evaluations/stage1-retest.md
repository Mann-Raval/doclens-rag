# Stage 1 retest — 2026-10-09

**Status: ready for a Cloud test deployment, not a v1.0 release.**

## Executed checks

- 31 offline tests passed, including upload replacement/removal, independent
  session state, real Chroma collection isolation, streaming, retry limits,
  evidence-ID rendering, and explicit word-limit handling.
- Two full 30-question live runs completed using the three original networking
  PDFs and `gemini-3.5-flash-lite`. The original model returned a 404 for the
  updated key, recommending this replacement. Deprecated temperature sampling
  was removed; the model remains configurable through `GEMINI_CHAT_MODEL`.
- The evidence-ID run completed all 30 with STOP finish reasons, one attempt
  each, and no API errors. The four missing-information cases all abstained.
- Six affected cases (13, 16, 19, 24, 25, 26) were then rerun after focused
  prompt/routing/length fixes; all completed without reference-marker warnings.
- Deterministic replay of saved evidence-ID responses validated reference
  membership for the 26 substantive answers. Four abstentions needed no citation.
  This replay fixed grouped IDs without another model call; it is not a fresh
  generation run or a claim-entailment score.

## Local timings

Evidence-ID run: Windows, Python 3.12.10, cached MiniLM, 184 chunks.

| Measurement | Result |
| --- | --- |
| Indexing | 9.04 s |
| First visible text, median / p95 | 2.31 / 10.02 s |
| Total answer latency, median / p95 | 4.30 / 11.97 s |

p95 is nearest rank across 30 sequential requests. These are local development
measurements, not Cloud or concurrency measurements. Cloud RAM remains unmeasured.

## Review findings and remaining risks

Answers were inspected for task coverage and citations, with source excerpts
checked for selected claims. This was not exhaustive independent adjudication
of every sentence, and no accuracy percentage is claimed.

| Cases | Findings |
| --- | --- |
| 1–12 | Factual/follow-up answers cover the intended concepts; grouped evidence IDs required renderer support. UDP header fields are explicitly present on chapter 3 page 6. |
| 13 | Retry now returns a full comparison, but the targeted run still attributes a chapter-3 checksum excerpt to chapter 1 in prose. |
| 14–18 | All summaries complete and cover requested subjects. A BGP/link-state conflation in case 16 was corrected in its targeted rerun. Some source notes contain questionable technical statements; summarizing them is not independent fact verification. |
| 19 | Original failing comparison returns a complete answer. Targeted review still finds unsupported cross-document attribution and HTTP/FTP status-code conflation. |
| 20–23 | Topic comparisons now retrieve focused evidence. TCP/UDP response acknowledges conflicting source claims about error checking. Supporting references do not guarantee every generalized statement is correct. |
| 24 | POP3/IMAP now retrieves both relevant pages (25–26), replacing the earlier false assertion that POP3 evidence was absent. |
| 25 | Requested chapters are covered, but a shared-ideas sentence still attributes chapter-2 OSPF material to chapter 1. |
| 26 | Targeted answer meets the 200-word prose limit (183 words, excluding rendered citations), but still mixes a chapter-1 IPv4/IPv6 detail into the chapter-2 description. |
| 27–30 | All four missing-information questions correctly abstain. |

**Known release blocker:** document attribution within comparison prose is not
consistently reliable, even when every cited marker identifies a real passage.
The deterministic renderer prevents invented filenames/pages from being silently
accepted; it does not verify that the cited evidence supports the claim.

### Correction to the initial report

The initial report incorrectly treated UDP fields as diagram-only/absent evidence.
Page 5 lacks the full field list in extracted text, but page 6 explicitly lists
source port, destination port, length, and checksum. The review criteria have
been corrected; the original abstention should not count as a correct answer.

## Next gates

1. Deploy the feature branch as a test candidate, using `docs/deployment.md`.
2. Measure Cloud latency/RAM and verify two real browser sessions, replacement,
   removal, streaming, and retries on that host.
3. Resolve remaining cross-document attribution defects and rerun affected cases;
   perform a final quality review on the release revision.
4. Only then merge and tag/publish `v1.0`.

Private reports and course excerpts remain under ignored
`evaluations/local-results/`; no keys or source PDFs are published. No release
or merge is claimed by this report.

## Deployed table-follow-up regression (build 1.3.1)

The owner supplied a Cloud screenshot and transcript showing successful upload
of three PDFs (184 passages), but "make difference table" switched to HTTP/HTTPS
and produced only an introduction. "make differnce table of 3 chapters" abstained.

The fix preserves the substantive question for format-only follow-ups, recognizes
the reported spelling, and permits Markdown tables when explicitly requested.
35 offline tests pass. A local live two-turn check with the original PDFs returned
STOP and complete five-line Markdown tables (header, separator, three document
rows) for both exact inputs: 12.55 s and 9.10 s total. The second answer retained
an invalid-reference warning; unsupported cross-document generalizations remain.
These are regression-generation checks, not evidence of perfect citation support.

The screenshot establishes that the app was deployed and used; deployed resource
measurements, browser isolation testing, and a Cloud retest of build 1.3.1 are
still pending. Course text and private answer artifacts remain uncommitted.

## Generic table scope correction (build 1.3.2)

The owner's next screenshot showed the explicit three-chapter table working but
the generic table request still abstaining. Routing checks reproduced a gap:
format-only follow-ups after collection summaries incorrectly used topic search.
With no preceding user question, the subject was also left unspecified.

The correction preserves collection scope after summaries/main topics/takeaways,
defaults subjectless table requests to uploaded PDFs, and keeps explicit topic
requests topic-scoped. Prior assistant answers are excluded from table prompts.
38 offline tests pass. Two local live scenarios (following a summary and starting
with no history) each exercised the generic and explicit requests; all four
returned STOP, five-line tables covering three chapters, and no marker warnings.
Their durations were 4.47/3.66 s and 3.36/3.45 s respectively. These checks verify
table generation and routing, not exhaustive claim support or deployed latency.
