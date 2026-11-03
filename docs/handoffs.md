# Explicit agent handoffs

Every `lab run` requires a YAML handoff packet. The run sends the recipient only the shared `LAB.md`, that role's prompt, and the contents of source files named by the packet. It does not pass prior agent conversations or load other repository files. A role's `reads:` metadata is a permission/topic boundary, not a file-loading mechanism.

## Packet format

```yaml
recipient: literature-scout
charter_item: H1
charter_source: research/charter.md
decisions:
  - decision: Search for prior work on the stated mechanism before proposing an experiment.
    reason: Novelty and the baseline choice depend on the closest prior work.
    source: research/pi-decisions/h1-scope.md
evidence:
  - research/charter.md
  - research/literature/search-protocol.md
task: >
  Identify the closest relevant prior work, report search methods and sources,
  and distinguish verified findings from unresolved questions.
expected_output: research/literature/h1-search.md
completion_test: >
  The artifact exists and includes search sources, query/date, relevant findings,
  citations, and explicit unknowns. Do not claim novelty.
```

`charter_source` must point to the charter file or another source containing the relevant charter item. `decisions` must contain at least one decision, reason, and source path. `evidence` may be empty. Every source path must resolve to a file inside the repository. The `recipient` must match the role passed to `lab run`, and `expected_output` must match `--out`. Model output is still checked for existence and non-empty content; the receiving coordinator must apply the stated completion test rather than treating a fluent response as proof of completion.

Run the packet with:

```bash
scripts/lab run literature-scout --handoff research/handoffs/h1-search.yaml --out research/literature/h1-search.md
```

The handoff artifact is the durable assignment record. `research/logs/audit.jsonl` additionally records the recipient role, model, assignment fields, handoff path and hash, hashes of included source files, and output path. It records the assignment rationale, not hidden model reasoning. Keep handoff packets and referenced source artifacts under version control to preserve a reviewable history.

Do not pass full conversations as sources. Summarize only the decisions and evidence needed for the task, preserve source paths, and identify uncertainty and disagreement explicitly. This limits inherited bias while retaining enough provenance for the next researcher to understand the assignment.
