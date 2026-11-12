# Design

## Context

See `proposal.md` for motivation. `lab-lead-swarm` established `roles/lab-lead.md`, Phase 0 (`scout`), native subagent `--prepare`/`--record` handoffs, `lab lit-search`, and `lab report-check`. This change adds the user-facing `.agents/skills/lab-*` workflow skills using **Approach B (Bounded 2-Wave Swarm + 1 Fact-Check Hop)**.

## Goals / Non-Goals

**Goals:**
- Provide pure-markdown slash-command skills in `.agents/skills/` (`/lab-scout`, `/lab-charter`, `/lab-investigate`, `/lab-promote`) analogous to `/openspec-*`.
- Enforce **Approach B (Bounded 2-Wave Swarm)** so subagents isolate noisy search/context and break self-sycophancy without smoothing over scientific disagreements in unbounded recursive loops.
- Allow at most **1 targeted subagent-to-subagent hop** strictly for factual verification when a reviewer flags `NEEDS NOVELTY CHECK`.

**Non-Goals:**
- Writing new Python code or modifying `scripts/lab.py` (this layer is 100% Markdown skills and role prompts calling the existing `scripts/lab` CLI).
- Unbounded recursive subagent debates (Approach A), which cause hallucination laundering, photocopy-of-a-photocopy detail loss, and watering down bold hypotheses into safe committee consensus.

## Decisions

### 1. Approach B: Bounded 2-Wave Swarm ("Expose the Clash") over Approach A (Unbounded Recursion)
- **Decision**: Structure `/lab-scout` and `/lab-investigate` around two bounded subagent waves plus an optional 1-hop factual lookup:
  - **Wave 1 (Build & Propose)**:
    1. `literature-scout` subagent runs `scripts/lab lit-search` and `scripts/lab cite-check`, writing `research/literature/<topic>.md` (absorbs raw search noise out of the Lab Lead's context).
    2. `pathfinder` subagent reads `research/literature/<topic>.md` and proposes 3–5 bold, falsifiable pathways + cheapest kill-tests in `research/pathways.md`.
  - **Wave 2 (Blind Attack + Max 1 Fact-Check Hop)**:
    1. `pathway-reviewer` / `adversarial-reviewer` runs in a **fresh, isolated subagent context** (`scripts/lab run --prepare` or `scripts/lab review --prepare`) seeing only the evidence packet—never the brainstorming conversation.
    2. If and only if the reviewer outputs `NEEDS NOVELTY CHECK: <specific query>`, 1 targeted `literature-scout` hop runs to verify whether prior work exists and updates `research/literature/<topic>.md`.
    3. `pathfinder` is **not** asked to water down its ideas to appease the reviewer; instead, both the bold pathways and the reviewer's exact objections flow up to `lab-lead` to be explained side-by-side in `research/reports/<topic>.md` (Sections 3 and 4).
- **Rationale**:
  - **Stops self-sycophancy**: A fresh reviewer subagent with zero memory of generating the idea attacks it honestly.
  - **Preserves pedagogical value**: The user learns how to think like a researcher by seeing *why* an idea might fail (confounders, unstated assumptions) and how the DIY Kill-Test isolates that risk.
  - **Prevents hallucination laundering**: Every subagent reads the primary `cite-check`-verified `research/literature/<topic>.md` table directly (max depth 2).
- **Alternatives considered**: Approach A (letting subagents recursively spawn subagents until consensus is reached), rejected because LLMs appease critics by making hypotheses vaguer and safer, hiding the scientific tension from the user.

### 2. Four Core `.agents/skills/lab-*` Slash Commands
- **Decision**: Create four skills matching the research lifecycle:
  1. `.agents/skills/lab-scout/SKILL.md` (`/lab-scout`): Runs Phase 0 (`scout`) via Approach B and outputs `research/reports/<topic>.md` + updates `research/glossary.md`, verified by `scripts/lab report-check` and `scripts/lab gate scout --topic <topic>`.
  2. `.agents/skills/lab-charter/SKILL.md` (`/lab-charter`): Takes a chosen pathway from a Phase 0 report, drafts `research/charter.md`, runs a blind `adversarial-reviewer` charter check, and verifies `scripts/lab gate charter`.
  3. `.agents/skills/lab-investigate/SKILL.md` (`/lab-investigate`): Runs Wave 1 builder (`literature-scout`, `theory-specialist`, `data-experiment-engineer`, or `writer`) and Wave 2 blind reviewer (`adversarial-reviewer`, `novelty-analyst`, `citation-auditor`, `proof-auditor`, `stats-methods-reviewer`) on a claim in `research/claims/claims.yaml`.
  4. `.agents/skills/lab-promote/SKILL.md` (`/lab-promote`): Runs the `integrity-officer` workflow (`scripts/lab promote` + `scripts/lab status`) and updates `research/session-state/checkpoint.md`.

## Risks / Trade-offs

- **[Risk] Subagents running on the same base model share model-level blind spots** -> **Mitigation**: All factual literature claims are gated by deterministic HTTP checks (`scripts/lab cite-check`), and users can still point the `reviewer` tier in `lab.yaml` to a second model vendor when running CLI-backed reviews.
