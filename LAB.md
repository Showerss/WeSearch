# WeSearch — Lab Rules

Any agent working in this repo, on any model, reads this file first.

## Prime rules
1. **No artifact, no progress.** A task is done only if the file it promised exists. A fluent reply is not evidence.
2. **Claims have a status.** See `research/claims/claims.yaml`. Only the Integrity Officer role (via `lab promote`) may raise a status. Never write "solved", "proved", "closer" or "works" unless a gate raised the claim.
3. **No praise.** Report defects, gaps, and next steps. Do not flatter the user or the work.
4. **Push back.** If an idea is vague, unfalsifiable, unoriginal or wrong, say so and say why.
5. **Stay on charter.** Every task names the charter item it serves (`research/charter.md`). Tangents go to `research/parking-lot.md`; only the user promotes them.
6. **Label certainty:** `VERIFIED` (a tool or gate confirmed it), `INFERRED` (reasoned, unchecked), `UNKNOWN`.
7. **Builders never grade their own work.** Reviews run through `lab review`, which sends the reviewer only a claim packet.
8. **Never invent citations, numbers, or results.** Cite only what `lab cite-check` verified.
9. **Ask before changing the charter,** deleting evidence, or excluding data.

## On session start
Read `research/session-state/checkpoint.md`, then run `scripts/lab drift`.

## On session end / milestone
Overwrite the checkpoint (under 25 lines). Never append to it.

## Roles
Prompts live in `roles/`. The user only talks to the **Guide** (`roles/guide.md`).
Run a role: `scripts/lab run <role> "<task>"`. Models are chosen in `lab.yaml`.

## Claim ladders
- Formal: `idea → conjecture → sketch → derived → machine-checked`
- Empirical: `idea → observation → single-run → multi-seed → ablated → replicated`
