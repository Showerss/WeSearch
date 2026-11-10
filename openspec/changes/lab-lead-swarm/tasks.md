# Tasks

## 1. Unified Lab Lead Role and Phase 0 Rules

- [ ] 1.1 Create `roles/lab-lead.md` combining the user-facing explanation, scope management, task planning, native subagent orchestration, and report synthesis responsibilities, and verify the file exists and includes its output and handoff contracts.
- [ ] 1.2 Update `lab.yaml`, `LAB.md`, `gates/phase-gates.md`, and `docs/handoffs.md` (plus deprecating/forwarding `roles/guide.md`, `roles/pi.md`, and `roles/postdoc.md`) to establish `lab-lead` as the sole user-facing coordinator and document Phase 0 (`scout`), verifying all role mappings resolve in `lab.yaml`.

## 2. Phase 0 Scouting & Native Subagent Bridge in `scripts/lab.py`

- [ ] 2.1 Extend `scripts/lab.py` handoff validation (`load_handoff`), `cmd_drift`, and `cmd_gate` to support Phase 0 (`scout` phase, `SCOUT:<topic>` charter items, and `scripts/lab gate scout --topic <topic>`), and verify with tests in `tests/test_lab.py` that Phase 0 handoffs and gates pass before `research/charter.md` is filled.
- [ ] 2.2 Add `--prepare <prompt-file>` and `--record` to `scripts/lab run` and `--prepare <packet-file>` and `--from-file <review-file>` to `scripts/lab review` so native coding-agent subagents can execute isolated handoff and review packets without external HTTP calls, and verify in `tests/test_lab.py` that prepared packets exclude unlisted files and recorded runs/reviews write valid `audit.jsonl` and review metadata.

## 3. Deterministic Literature Search (`lab lit-search`)

- [ ] 3.1 Implement `scripts/lab lit-search "<query>" [--max N] [--out <path>]` in `scripts/lab.py` using stdlib `urllib.request` against arXiv and CrossRef APIs, and update `roles/literature-scout.md` to use `lab lit-search` and `lab cite-check`, verifying in `tests/test_lab.py` (with mocked/local HTTP responses) that returned entries format cleanly with valid `arxiv:` / `doi:` IDs.

## 4. ELI5 & Jargon-Translated Research Reports (`lab report-check`)

- [ ] 4.1 Create `research/reports/` template/conventions and implement `scripts/lab report-check <file>` in `scripts/lab.py` to enforce the 5 mandatory report sections, diagram presence, `### Jargon Decoder` synchronization with `research/glossary.md`, citation resolution, and certainty labels.
- [ ] 4.2 Add unit and integration tests for `lab report-check` (both passing reports and reports missing sections, glossary entries, or verified citations) in `tests/test_lab.py` and document the report workflow in `README.md`, verifying `python3 tests/test_lab.py` passes end-to-end.
