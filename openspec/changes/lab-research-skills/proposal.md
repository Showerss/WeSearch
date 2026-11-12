# Proposal

## Why

With `lab-lead-swarm` providing the underlying `roles/lab-lead.md` and `scripts/lab.py` enforcement primitives, WeSearch still lacks an "OpenSpec for Research" slash-command skill layer in `.agents/skills/` that orchestrates subagent waves automatically. Furthermore, unbounded recursive subagent loops risk watering down bold hypotheses into committee consensus and losing paper details across summarization hops, whereas a **Bounded 2-Wave Swarm (Approach B)** exposes both bold ideas and independent reviewer attacks directly to the user.

## What Changes

- Introduce markdown-only agent workflow skills under `.agents/skills/` (and corresponding agent command wrappers) that provide slash commands for research stages:
  - `/lab-scout`: Runs the **Approach B Bounded 2-Wave Swarm** on a topic (Wave 1: `literature-scout` + `pathfinder`; Wave 2: blind `pathway-reviewer` / `adversarial-reviewer` attack + at most 1 targeted `literature-scout` novelty-check hop) and synthesizes the 5-part ELI5 + Jargon-Decoded Report (`research/reports/<topic>.md`).
  - `/lab-charter`: Graduates a chosen research angle from a Phase 0 report into `research/charter.md`, runs an independent adversarial charter review, and checks `scripts/lab gate charter`.
  - `/lab-investigate`: Dispatches builder subagents and blind reviewer subagents for a specific charter claim (`research/claims/claims.yaml`) using `scripts/lab run --prepare/--record` and `scripts/lab review --prepare/--from-file`.
  - `/lab-promote`: Runs the Integrity Officer check and `scripts/lab promote` when all required reviews and evidence gates pass.
- Update subagent role prompts (`roles/pathfinder.md`, `roles/pathway-reviewer.md`, `roles/literature-scout.md`, `roles/lab-lead.md`) to enforce the **Bounded 2-Wave + 1 Fact-Check Hop (Approach B)** rule: preserve sharp disagreements between builders and reviewers rather than rewriting ideas into safe mediocrity behind the scenes.

## Capabilities

### New Capabilities
- `lab-research-skills`: Markdown slash-command skills (`.agents/skills/lab-*/SKILL.md`) implementing the Bounded 2-Wave Swarm (Approach B) for topic scouting, charter locking, claim investigation, and promotion.

### Modified Capabilities
- `lab-lead-workflow`: Bound subagent delegation depth to 2 waves plus at most 1 targeted `NEEDS NOVELTY CHECK` literature lookup hop so disagreements between builders and reviewers are surfaced directly in the user's report.

## Impact

- **Markdown skills (no Python code required)**: `.agents/skills/lab-scout/SKILL.md`, `.agents/skills/lab-charter/SKILL.md`, `.agents/skills/lab-investigate/SKILL.md`, `.agents/skills/lab-promote/SKILL.md`.
- **Role prompts**: `roles/lab-lead.md`, `roles/pathfinder.md`, `roles/pathway-reviewer.md`.
