# Study protocol (preregistration)

> Fill in BEFORE any run. Freeze with `scripts/lab prereg`. After freezing, changes require `scripts/lab prereg --amend "<reason>"`, which is logged in `research/amendments.md`.
> Replace every `(...)` placeholder. Exploratory analyses done later must be labelled exploratory.

## Hypotheses under test
(Copy H-ids from the charter, with the exact falsifier and the metric/threshold that decides it.)

## Datasets and provenance
(Name, version, URL, license, hash, train/validation/test split and how it is fixed. How contamination with pretraining data is checked.)

## Methods and baselines
(Proposed method, strongest current baselines with citations, and the equal tuning budget for each.)

## Metrics
(Primary metric, secondary metrics, why each matches the hypothesis.)

## Seeds, compute and budget
(Number of seeds, at least 5 for multi-seed claims. Hardware, wall-clock and cost limits.)

## Statistical analysis plan
(Tests or intervals, effect-size measure, multiple-comparison correction, what counts as a meaningful difference. Fixed before seeing results.)

## Stopping rules and exclusions
(When runs stop. What data or runs may be excluded and by what rule. Nothing else may be excluded.)

## Threats to validity
(Internal, external, construct and conclusion validity: leakage, benchmark saturation, hyperparameter sensitivity, implementation bugs, narrow generalization.)

## Negative-result plan
(What gets reported and how if the hypothesis is falsified or the result is null.)

## Ethics, licensing and responsible use
(Dataset and model licenses, personal data, consent or IRB-equivalent review if applicable, misuse risks, environmental cost.)

## Reproducibility and artifacts
(Code and data release plan, environment pinning, checklist used, e.g. ML Reproducibility Checklist or ACM artifact badging.)
