# Known-flaw regression cases for reviewers

A reviewer that approves any of these is broken: swap its model or fix its prompt.
Run each as a claim (`lab claim add`, put the text under `research/claims/<id>/`), then `lab review <id> <role>`.
Expected verdict is never `VERIFIED`.

| Case | Role | Flaw | Expected |
|---|---|---|---|
| `flawed-proof-1.md` | proof-auditor | Induction with no base case | GAP or REFUTED |
| `flawed-proof-2.md` | proof-auditor | "Clearly" hides an unjustified step | GAP |
| `weak-experiment-1.md` | stats-methods-reviewer | One seed, untuned baseline, tuned on test set | UNSUPPORTED |
| `overclaim-1.md` | adversarial-reviewer | "State of the art" with no comparison | UNSUPPORTED |

Add real cases from your field over time. Record each reviewer's result here with the date and model.
