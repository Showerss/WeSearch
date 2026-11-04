# WeSearch diagrams

## Overview: who writes what, where
```mermaid
flowchart LR
  U[User] --> G[Guide]
  G -->|checkpoint, glossary, diagrams| F1[(research/session-state, glossary.md, diagrams/)]
  PI[PI] -->|charter, parking lot| F2[(research/charter.md, parking-lot.md)]
  PI -->|raw ideas| F3[(research/ideas/)]
  U -->|raw ideas| F3
  PF[Pathfinder] --> F4[(research/pathways.md)]
  F3 -->|raw material| PF
  PD[Postdoc] -->|plan + explicit handoff packets| F5[(research/plan.md, research/handoffs/)]
  PD -->|checks artifact against completion test| PF
  LS[Literature Scout] --> F6[(research/literature/)]
  DE[Data/Experiment Eng.] --> F7[(research/runs/, src/)]
  TS[Theory Specialist] --> F8[(research/claims/ID/)]
  W[Writer] --> F9[(research/drafts/)]
  PF & LS & DE & TS & W -->|artifact + status| PD
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
  participant PD as Postdoc
  participant LS as Lit Scout
  participant AR as Adversarial Reviewer
  S->>G: "I want to research X"
  G->>PI: topic, in plain words
  PI->>PI: sharpen topic into falsifiable hypotheses
  PI-->>G: charter draft -> research/charter.md
  G->>AR: review charter
  AR-->>G: verdict (lab gate charter must pass)
  G->>S: restate charter, student approves
  PI->>PD: decision memo + charter item
  PD->>PD: create plan and explicit handoff packet
  PD->>LS: lab run --handoff packet.yaml --out research/literature/topic.md
  Note over LS: Receives shared LAB.md, role prompt, and only packet-listed source files, with no prior conversations
  LS-->>PD: artifact + run status
  PD->>PD: check artifact against handoff completion test
  PD-->>PI: artifact, completion assessment, blockers
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
  G->>PI: request scope decision
  PI-->>G: charter item and decision memo
  G->>PD: route approved task and decision memo
  PD->>PF: explicit packet with charter, decisions, evidence, task, output, completion test
  Note over PF: Receives only shared policy, role prompt, and named packet sources
  PF-->>PD: research/pathways.md (3-5 paths, each with cheapest kill-test)
  PD->>PD: check artifact against completion test
  PD->>PR: explicit reviewer packet with pathway and evidence bundle
  Note over PR: Independent review, using packet sources only and no prior conversations
  PR-->>PD: PURSUE/HOLD/REJECT, objections tagged EVIDENCE or SPECULATION
  PD->>PD: check review artifact and route novelty questions
  PD->>LS: explicit packet for novelty literature search
  LS->>NA: evidence artifact for independent novelty assessment
  NA-->>PD: novelty verdict artifact
  PD-->>G: checked artifacts, verdicts, blockers
  G-->>R: 3 pathways + verdicts
  R->>G: picks one (only the user promotes it to the charter)
  G->>PI: user choice for charter decision
  PI->>PD: approved scope decision
  PD->>DE: explicit packet, then lab run --handoff packet.yaml
  DE-->>PD: artifact + run status
  PD->>PD: check artifact against completion test
```
