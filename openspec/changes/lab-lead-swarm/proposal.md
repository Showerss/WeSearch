# Proposal

## Why

WeSearch currently requires a locked, falsifiable `research/charter.md` before any subagent can run, splits management across three separate roles (`guide`, `pi`, `postdoc`), and relies on single-shot, zero-tool HTTP model calls in `scripts/lab.py` that cannot search literature or orchestrate a subagent swarm. Users who want to explore a new research field from scratch need to talk to a single **Lab Lead** that delegates literature scouting, idea generation, and adversarial critique to native subagents and returns an understandable, jargon-translated research report (`research/reports/<topic>.md`) that equips them to conduct their own research.

## What Changes

- **BREAKING**: Collapse the three management roles (`roles/guide.md`, `roles/pi.md`, `roles/postdoc.md`) into a single user-facing **Lab Lead** role (`roles/lab-lead.md`) that owns planning, subagent delegation, glossary maintenance, and report synthesis while preserving strict separation from independent reviewers (`adversarial-reviewer`, `pathway-reviewer`, `novelty-analyst`, `citation-auditor`) and the `integrity-officer`.
- Add **Phase 0 (Field Scouting)** so the Lab Lead and subagent swarm (`literature-scout`, `pathfinder`, `pathway-reviewer`, `novelty-analyst`, `adversarial-reviewer`) can explore a broad topic before `research/charter.md` has a locked hypothesis.
- Update `scripts/lab.py` to support native subagent execution (preparing isolated handoff/review packets and recording/verifying subagent outputs and review verdicts without requiring external OpenAI-compatible HTTP calls) and add a deterministic literature search helper (`lab lit-search`) querying arXiv and CrossRef so `literature-scout` subagents retrieve real, verifiable papers and abstracts.
- Introduce a persistent **ELI5 & Jargon-Translated Research Report** workflow (`research/reports/<topic>.md`) that synthesizes subagent findings into: (1) a 5-year-old mental model + diagram, (2) a plain-English landscape of prior work with an Academic Jargon Decoder table and `cite-check`-verified papers, (3) reviewer hole-poking findings, (4) original research angles with step-by-step "do-it-yourself" kill-tests, and (5) an active-learning check-in.

## Capabilities

### New Capabilities
- `lab-lead-workflow`: Single Lab Lead orchestration, Phase 0 pre-charter topic scouting, native subagent handoff/review packet preparation and recording, and deterministic literature search (`lab lit-search`).
- `eli5-research-reports`: Structure, jargon-translation rules, citation verification, and active-learning requirements for producible research reports in `research/reports/<topic>.md` and `research/glossary.md`.

### Modified Capabilities
<!-- No existing specs in openspec/specs/ -->

## Impact

- **Role prompts & rules**: `LAB.md`, `README.md`, `roles/lab-lead.md` (replacing/unifying `roles/guide.md`, `roles/pi.md`, `roles/postdoc.md`), `roles/literature-scout.md`, `gates/phase-gates.md`, `lab.yaml`.
- **CLI enforcement (`scripts/lab.py`)**: Add Phase 0 (`scout`) support in handoffs and drift/gate checks, native subagent packet preparation and output/verdict recording (`--prepare` / `--record`), and `lab lit-search` for arXiv/CrossRef retrieval.
- **Research artifacts**: New `research/reports/` directory convention and updated `research/glossary.md` jargon decoder integration.
- **Tests (`tests/test_lab.py`)**: Add tests covering Phase 0 scouting handoffs, native subagent packet/record flows, `lit-search`, and report validation.
