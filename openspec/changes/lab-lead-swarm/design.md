# Design

## Context

See `proposal.md` for motivation. Currently, `scripts/lab.py` assumes:
1. Every `lab run` and `lab review` invokes `call_model()` over HTTP using API keys from `lab.yaml` (`CHANGE_ME` by default), with no tool access for subagents.
2. Three separate coordination roles (`guide`, `pi`, `postdoc`) sit between the user and the builder/reviewer roles.
3. No subagent can run until `research/charter.md` has a locked hypothesis (`H1`), blocking pre-charter topic scouting.
4. No persistent report artifact exists to translate subagent findings and academic jargon into a beginner-friendly, actionable research guide.

## Goals / Non-Goals

**Goals:**
- Unify `guide`, `pi`, and `postdoc` into `roles/lab-lead.md` while keeping backward compatibility in `lab.yaml` and `scripts/lab.py` for existing tests.
- Enable native coding-agent subagents (Option A execution engine) to run with strict context isolation and blind review packets via `--prepare` and `--record` / `--from-file` modes on `scripts/lab`.
- Add deterministic arXiv + CrossRef search (`scripts/lab lit-search`) using only Python standard library (`urllib.request`, `xml.etree.ElementTree`, `json`) so zero extra pip dependencies beyond `PyYAML` are needed.
- Support Phase 0 (`scout`) handoffs and gate checks before `research/charter.md` is populated.
- Enforce the 5-part ELI5 + Jargon Decoder report contract via `scripts/lab report-check`.

**Non-Goals:**
- Building a custom multi-turn LLM tool-calling loop inside `scripts/lab.py` (the active coding agent and its native subagents provide the runtime).
- Weakening claim promotion gates (`lab promote` and `gates/requirements.yaml` remain strictly enforced by the Integrity Officer and independent reviewers).

## Decisions

### 1. Native Subagent Bridge (`--prepare` and `--record` / `--from-file`) in `scripts/lab.py`
- **Decision**: Extend `scripts/lab run` with `--prepare <prompt_out>` and `--record`, and extend `scripts/lab review` with `--prepare <packet_out>` and `--from-file <review_in>`. Keep the default HTTP `call_model()` path intact when neither flag is passed.
- **Rationale**: In an agentic coding environment, the Lab Lead spawns native subagents (`invoke_subagent`) that already have tool access. Using `scripts/lab run ... --prepare` guarantees the subagent still receives only the validated handoff packet (`LAB.md`, role prompt, and hashed source files), and `--record` hashes the inputs/outputs into `research/logs/audit.jsonl`. Similarly, `scripts/lab review ... --prepare` builds the blind review packet (hiding author conversation), and `--from-file` parses the subagent's verdict into `research/logs/reviews/<claim>/`. Keeping the legacy HTTP mode ensures `tests/test_lab.py` continues to pass alongside new tests.
- **Alternatives considered**: Replacing `call_model()` entirely with CLI subagent calls (rejected because `scripts/lab.py` is model-agnostic and headless tests rely on the HTTP mock server).

### 2. Unifying `guide`, `pi`, and `postdoc` into `roles/lab-lead.md`
- **Decision**: Create `roles/lab-lead.md` as the primary user-facing orchestrator in `LAB.md` and `lab.yaml`. Retain `roles/guide.md`, `roles/pi.md`, and `roles/postdoc.md` as thin deprecated aliases pointing to `roles/lab-lead.md` so existing scripts or references do not break.
- **Rationale**: Eliminates two intermediate handoff layers (`Guide -> PI -> Postdoc`) that added friction without adding independent verification. Scientific rigor comes from independent reviewers (`adversarial-reviewer`, `pathway-reviewer`, `novelty-analyst`, `citation-auditor`) seeing only blind packets, not from splitting task planning across three managers.

### 3. Phase 0 (`scout`) Handoff and Gate Mechanics
- **Decision**:
  - Allow `charter_item` in handoffs to use `SCOUT:<topic>` when `charter_source` points to either `research/charter.md` or a topic brief `research/reports/<topic>-brief.md`.
  - Add `scout` to `scripts/lab gate {scout,charter,protocol,data,analysis,draft,submission}` (with `--topic <topic>` for `scout`).
  - Update `scripts/lab drift` so that if `Current phase: scout` is set in `research/session-state/checkpoint.md`, drift is evaluated against the active scouting topic rather than failing with exit code 4 on an empty charter.
- **Rationale**: Resolves the Day 0 catch-22 where a beginner cannot formulate a falsifiable hypothesis in `research/charter.md` before scouting what has and hasn't been done.

### 4. Stdlib-Only `lab lit-search` Command
- **Decision**: Implement `scripts/lab lit-search "<query>" [--max 10] [--out <json/md>]` in `scripts/lab.py` querying the arXiv Atom API (`export.arxiv.org/api/query?search_query=...`) and CrossRef REST API (`api.crossref.org/works?query=...`) via `urllib.request`.
- **Rationale**: `scripts/lab.py` already queries both APIs by ID in `cmd_cite_check`. Adding search query support uses the exact same zero-dependency stack and prevents `literature-scout` subagents from fabricating citations or DOIs.

### 5. Mechanical Validation of ELI5 Reports (`lab report-check`)
- **Decision**: Add `scripts/lab report-check <report.md>` which verifies:
  1. Presence of all 5 required headings (`## 1. Mental Model`, `## 2. What Has Already Been Done`, `## 3. Where the Holes Are`, `## 4. Original Research Ideas & DIY Kill-Tests`, `## 5. Active Learning Check-In`).
  2. Presence of an ASCII or Mermaid diagram block in Section 1.
  3. Presence of the `### Jargon Decoder` markdown table in Section 2, with every decoded term present in `research/glossary.md`.
  4. All DOIs/arXiv IDs cited in the report exist in a `research/literature/*.md` table or pass `cite-check` (unless marked `UNVERIFIED`).
  5. Presence of certainty labels (`VERIFIED`, `INFERRED`, `UNKNOWN`).
- **Rationale**: Prime rule 1 of `LAB.md` is "No artifact, no progress." Mechanical enforcement guarantees the Lab Lead never hands back an unstructured chat summary or untranslated academic jargon in place of a complete report.

## Risks / Trade-offs

- **[Risk] Native subagents might read unlisted repository files during a blind review if spawned in the shared workspace** -> **Mitigation**: In `roles/lab-lead.md` and reviewer role prompts, enforce that reviewer subagents receive the prepared packet (`research/logs/packets/<id>.md`) and are instructed to read only that packet file, while `scripts/lab review --from-file` records the exact `packet_hash` audited.
- **[Risk] Public arXiv/CrossRef APIs rate-limit or fail when offline** -> **Mitigation**: `lab lit-search` sets a clear `User-Agent`, handles network timeouts gracefully with a non-zero exit code and diagnostic message, and allows native subagents to fall back to web search tools followed by `lab cite-check`.
