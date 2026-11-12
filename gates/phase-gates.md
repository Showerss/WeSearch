# Phase gates

A phase passes only when every item is true AND the user has restated the decision to the Lab Lead in their own words. Run `scripts/lab gate <phase>` for the mechanical checks (`scripts/lab gate scout --topic <topic>` for Phase 0).

| Phase | Must be true |
|---|---|
| 0. scout | Pre-charter field scouting on `<topic>`: cite-checked literature table (`research/literature/<topic>.md`), pathways (`research/pathways.md`), independent pathway review (`research/logs/pathway-review.md` or `research/logs/pathway-review-<topic>.md`), and a 5-part ELI5 + jargon-decoded report (`research/reports/<topic>.md`) passing `lab report-check`. |
| 1. charter | Main question, falsifiable hypotheses (each with a falsifier), success and stop criteria, out-of-scope list, keywords. Adversarial reviewer returned VERIFIED on the charter (is it falsifiable, specific, motivated, new?). |
| 2. protocol | Literature table exists; every entry passed `cite-check` or is marked UNVERIFIED and excluded. Novelty analyst verdict recorded. `research/lit-protocol.md` and `research/protocol.md` complete and frozen with `lab prereg` before any run (methods, baselines, datasets, metrics, stats plan, threats to validity, ethics/licensing). Assumptions listed. |
| 3. data | Dataset provenance and hashes recorded. Train/test separation documented. |
| 4. analysis | Every claim in scope has status at or above its target rung. No open critical defect. Replication done for headline claims. |
| 5. draft | Citation Auditor verdict VERIFIED on claims resting on literature. Limitations, threats to validity and negative results sections present. |
| 5. draft (mechanical) | `lab draft-check` passes: every number has a run ID, every claim tag is within its status, every citation verified, every figure has a script. |
| 6. submission | Integrity Officer sign-off logged. Final drift check is `on-track`. User confirms understanding of each headline claim and its weakest point. |

## Charter review prompt (for the adversarial reviewer)
Is the main question answerable by evidence? Is each hypothesis falsifiable, and is the falsifier stated? Could a real result contradict it? Is the scope bounded and the out-of-scope list real? Is it distinguishable from existing work? List defects with severity. Verdict: VERIFIED | GAP | UNSUPPORTED | REFUTED.
