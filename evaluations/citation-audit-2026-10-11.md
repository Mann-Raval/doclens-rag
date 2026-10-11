# Manual comparison citation audit

Scope: the user's Chapter 1 versus Chapter 2 comparison from build 1.3.12,
checked against the source excerpts pasted on 2026-10-11. This is an excerpt
audit, not independent inspection of the original PDF pages or an external
networking fact-check. Reference numbers below belong only to that answer.

| Sampled claim | References | Finding |
| --- | --- | --- |
| Interconnected devices exchange data | [1], Chapter 1 p.1 | Supported |
| TCP/IP and switching are covered | [5, 6], Chapter 1 pp.19, 42 | Supported |
| Framing, MAC addressing, error control | [9], Chapter 1 p.13 | Supported |
| Error detection and medium access | [2, 3], Chapter 2 pp.1, 20 | Supported |
| BGP, OSPF and subnetting are covered | [8], Chapter 2 p.32 | Supported |
| Parity, CRC applications and BGP/OSPF examples | [16, 11, 8], Chapter 2 pp.5, 9, 32 | Supported |
| Static or dynamic shortest-path routing | [13, 4], Chapter 2 pp.23, 26 | Partial: static routing and shortest paths explicit; dynamic qualifier insufficiently established |
| Ethernet cables example | [14, 6, 15], Chapter 1 pp.6, 42, 59 | Partial: explicit cable evidence is p.1, not these cited excerpts |

Six supported and two partial sampled claims is not an overall accuracy score.
The remainder of the answer and other application routes were not audited here.

## Corrected wording for the two sampled claims

- Chapter 1 examples: Ethernet and Wi-Fi networks, IPv4/IPv6 addresses, and
  website requests traversing switches and routers (Chapter 1 pp.6, 42, 59).
  If describing Ethernet **cables**, additionally cite Chapter 1 p.1.
- Chapter 2 routing: static routing and shortest-path selection (Chapter 2
  pp.23, 26). Omit the dynamic qualifier unless an explicitly supporting
  excerpt is retrieved and cited.

These are audited corrections, not replacements silently applied to old chats.

## Source inconsistency

Chapter 2 p.29 labels OSPF distance-vector; p.32 labels it link-state. The
application must not equate faithful source attribution with factual truth.
This audit records the disagreement without resolving it from external sources.

## Build 1.3.13 change and limits

Comparison instructions now require item-level support from the cell's own
references, discourage unsupported qualifiers and technology-to-medium expansion,
and ask for source disagreements to be disclosed or disputed details omitted.
Existing deterministic checks still validate reference ownership and schema,
NOT semantic entailment. Prompt instructions cannot guarantee claim support.
No extra model-review call or automatic rewrite of existing chats was added.

Regression tests check the new prompt contract and reject an exact supporting
span attributed to the wrong excerpt. The latter validates the optional quote
validator, not semantic correctness of arbitrary generated paraphrases.

Release remains pending fresh generated-answer verification and final release
checks. This audit does not authorize calling the model output fully verified.

## Validation result

All 78 automated tests passed on 2026-10-11 (6.634 seconds). A fresh live run of
network evaluation case 25 indexed 184 chunks in 12.02 seconds and completed
the two-chapter comparison in 11.37 seconds with STOP and no reference-membership
warning. All eight cells were filled. Private output is retained in the ignored
`evaluations/local-results/network-citation-audit-1313.json` report.

The fresh output avoided the prior unsupported dynamic-routing qualifier and
Ethernet-cable example. However, manual review found additional support gaps:

- Chapter 1 Key concepts mentions protocol layers but cites pp.1, 52, 55;
  the supplied p.19 excerpt would be a more appropriate supporting reference.
- Chapter 2 Mechanisms mentions distance-vector routing but cites pp.1, 9,
  12, 20, 32; these excerpts do not clearly establish that item. Page 32's
  path-vector description is not interchangeable with distance-vector.

Outcome: completeness and reference membership passed in this single run;
claim-level citation support did not. The prompt change is an incremental
instruction improvement, not a verified repair of semantic citation accuracy.
Do not merge/tag v1.0 on the strength of this run. Original PDF page inspection
and a reliable claim-support strategy remain outside what this run establishes.
