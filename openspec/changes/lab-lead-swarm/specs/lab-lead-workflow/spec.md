# Spec Delta

## Purpose

Defines the unified Lab Lead orchestration role, Phase 0 pre-charter topic scouting workflow, native subagent packet preparation and output recording, and deterministic literature retrieval so a user can explore a research topic with a subagent swarm before or after locking a charter.

## ADDED Requirements

### Requirement: Single User-Facing Lab Lead Role
The system SHALL provide a unified `lab-lead` role (`roles/lab-lead.md`) that serves as the sole user-facing coordinator, combining plain-language explanation, research scope management, task planning, and subagent delegation while remaining prohibited from raising claim statuses or reviewing its own claims.

#### Scenario: User initiates topic exploration with Lab Lead
- **WHEN** the user asks to explore a research topic or plan an investigation
- **THEN** the `lab-lead` role coordinates subagent handoffs (`literature-scout`, `pathfinder`, independent reviewers) and synthesizes findings directly for the user without requiring separate `guide`, `pi`, or `postdoc` handoff hops

#### Scenario: Lab Lead is blocked from grading claims
- **WHEN** a claim requires review or status promotion
- **THEN** the system requires an independent reviewer role (`adversarial-reviewer`, `pathway-reviewer`, `novelty-analyst`, `citation-auditor`, `proof-auditor`, `stats-methods-reviewer`, or `replicator`) and the `integrity-officer` via `lab promote`, rejecting self-review by `lab-lead`

### Requirement: Phase 0 Pre-Charter Field Scouting
The system SHALL support a `scout` phase (Phase 0) that allows `literature-scout`, `pathfinder`, and reviewer handoffs to run on a broad exploration topic before `research/charter.md` has locked falsifiable hypotheses.

#### Scenario: Running a Phase 0 scouting handoff without a locked charter
- **WHEN** a handoff packet specifies `phase: scout` (or `charter_item: SCOUT:<topic>`) and points `charter_source` to a scouting brief or topic file
- **THEN** `scripts/lab` accepts the handoff and records `phase: "scout"` in `research/logs/audit.jsonl` even if `research/charter.md` still contains template placeholders

#### Scenario: Checking Phase 0 gate completion
- **WHEN** the user or Lab Lead runs `scripts/lab gate scout --topic <topic>`
- **THEN** the CLI verifies that a cite-checked literature file (`research/literature/<topic>.md`), a pathways file (`research/pathways.md`), a pathway review (`research/logs/pathway-review.md` or topic-specific review), and a synthesized report (`research/reports/<topic>.md`) exist and are non-empty

### Requirement: Native Subagent Packet Preparation and Recording
The system SHALL allow `scripts/lab` to prepare context-isolated handoff and review prompts for native coding-agent subagents and record their completed outputs and verdicts into the audit log without requiring external OpenAI HTTP calls.

#### Scenario: Preparing an isolated subagent handoff prompt
- **WHEN** `scripts/lab run <role> --handoff <packet.yaml> --out <path> --prepare <prompt-file>` is executed
- **THEN** the CLI validates all handoff fields and in-repo source paths, writes the assembled context-isolated prompt (including `LAB.md`, role instructions, and explicit source contents) to `<prompt-file>`, and exits 0 without making an external HTTP request

#### Scenario: Recording a native subagent handoff output
- **WHEN** a native subagent writes `<path>` and `scripts/lab run <role> --handoff <packet.yaml> --out <path> --record` is executed
- **THEN** the CLI verifies `<path>` exists and is non-empty, hashes the handoff and source files, and appends the `run` event to `research/logs/audit.jsonl`

#### Scenario: Preparing and recording an independent claim review from a native subagent
- **WHEN** `scripts/lab review <claim-id> <reviewer-role> --prepare <packet-file>` is followed by a native reviewer subagent writing its review and `scripts/lab review <claim-id> <reviewer-role> --from-file <review-output-file>`
- **THEN** the CLI builds the blind claim packet (excluding author reasoning), parses the reviewer's `VERIFIED | GAP | UNSUPPORTED | REFUTED` verdict from `<review-output-file>`, writes the timestamped review with `packet_hash` metadata under `research/logs/reviews/<claim-id>/`, and records the `review` event in `research/logs/audit.jsonl`

### Requirement: Deterministic Literature Search Helper
The system SHALL provide a `scripts/lab lit-search <query>` command that queries public bibliographic APIs (arXiv and CrossRef) and outputs verifiable paper metadata (title, authors, year, venue/source, arXiv ID or DOI, and abstract excerpt) so `literature-scout` subagents can ground literature tables in real identifiers.

#### Scenario: Searching literature with verifiable identifiers
- **WHEN** `scripts/lab lit-search "<query>"` is executed
- **THEN** the CLI returns matching entries with real `arxiv:` or `doi:` identifiers and abstract snippets that pass `scripts/lab cite-check`
