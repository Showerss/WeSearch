# WeSearch diagrams

## Overview: who writes what, where
```mermaid
flowchart LR
  U[User] --> G[Guide]
  G -->|checkpoint, glossary, diagrams| F1[(research/session-state, glossary.md, diagrams/)]
  PI[PI] -->|charter, parking lot| F2[(research/charter.md, parking-lot.md)]
  ID[Ideator] --> F3[(research/ideas/)]
  PF[Pathfinder] --> F4[(research/pathways.md)]
  PD[Postdoc] -->|plan + briefs via lab run| F5[(research/plan.md)]
  LS[Literature Scout] --> F6[(research/literature/)]
  DE[Data/Experiment Eng.] --> F7[(research/runs/, src/)]
  TS[Theory Specialist] --> F8[(research/claims/ID/)]
  W[Writer] --> F9[(research/drafts/)]
  F6 & F7 & F8 -->|claim packet only| REV[Independent reviewers]
  REV -->|verdict| F10[(research/logs/reviews/)]
  F10 --> IO[Integrity Officer: lab promote]
  IO --> CL[(claims.yaml)]
  CL --> G
```

## Story 1: new student forms a thesis
```mermaid
sequenceDiagram
  actor S as Student
  participant G as Guide
  participant PI
  participant ID as Ideator
  participant PD as Postdoc
  participant LS as Lit Scout
  participant AR as Adversarial Reviewer
  S->>G: "I want to research X"
  G->>PI: topic, in plain words
  PI->>ID: generate ideas
  ID-->>PI: research/ideas/*.md (each with a falsifier)
  PI-->>G: charter draft -> research/charter.md
  G->>AR: review charter
  AR-->>G: verdict (lab gate charter must pass)
  G->>S: restate charter, student approves
  PD->>LS: lab run --out research/literature/topic.md
  LS-->>PD: lit table, cite-check run
  PD->>PD: fill lit-protocol + protocol, lab prereg (freeze)
  PD-->>G: research/plan.md + status
  G-->>S: next steps, checkpoint saved
```

## Story 2: check progress and falsifiability
```mermaid
sequenceDiagram
  actor R as Researcher
  participant G as Guide
  participant L as lab CLI
  participant PI
  participant AR as Adversarial Reviewer
  participant IO as Integrity Officer
  R->>G: "Are my claims falsifiable? Where are we?"
  G->>L: lab start, lab status, lab drift
  L-->>G: checkpoint, claim ladder, drift
  G->>PI: check claims vs charter falsifiers
  PI-->>G: decision memo (vague claims named, what's missing)
  G->>L: lab review claim adversarial-reviewer
  L->>AR: claim packet only (no author reasoning)
  AR-->>L: VERIFIED / GAP / UNSUPPORTED / REFUTED
  L-->>IO: verdicts stored, stale if evidence changed
  IO-->>G: promote allowed or blocked, with reason
  G-->>R: defects and gaps, no praise
```

## Story 3: three pathways for a Java test program
```mermaid
sequenceDiagram
  actor R as Researcher
  participant G as Guide
  participant PF as Pathfinder
  participant LS as Lit Scout
  participant PR as Pathway Reviewer
  participant NA as Novelty Analyst
  participant DE as Data/Experiment Eng.
  R->>G: "3 ways to build a Java program to test H1"
  G->>PF: lab run pathfinder
  PF-->>G: research/pathways.md (3-5 paths, each with cheapest kill-test)
  G->>PR: charter summary + pathway + evidence bundle
  PR-->>G: PURSUE/HOLD/REJECT, objections tagged EVIDENCE or SPECULATION
  PR->>LS: NEEDS NOVELTY CHECK
  LS->>NA: literature table
  NA-->>G: novelty verdict
  G-->>R: 3 pathways + verdicts
  R->>G: picks one (only the user promotes it to the charter)
  G->>DE: later: lab run, writes src/ and research/runs/
```
