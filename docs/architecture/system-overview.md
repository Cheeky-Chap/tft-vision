# TFT Vision system overview

## Purpose

TFT Vision turns user-controlled Windows screen captures or user-provided offline media into
bounded observations and review artifacts. It is a recognition and advisory project, not a
game-control system.

## Data flow

```text
Windows desktop or owned offline media
  -> capture / video ingest
  -> calibrated game region and ROI crops
  -> deterministic recognizers
  -> Observation values and GameStateSnapshot
  -> offline reports or localhost-only review UI
  -> human verification
```

Runtime captures, crops, videos, labels, reports, and model artifacts remain outside Git.
The repository contains source, deterministic fixtures, static aliases, tests, and policy
documents only.

## Component ownership

| Area | Responsibility | Verification boundary |
| --- | --- | --- |
| `src/capture/` | user-initiated Windows capture | Windows desktop verification required |
| `src/crop/` | game-region and ROI extraction | static tests plus manual visual inspection |
| `src/recognition/` | bounded observations with confidence/status | deterministic unit tests and owned samples |
| `src/state/` | structured snapshot contracts | unit and schema tests |
| `src/video_ingest/` | offline media ingestion | synthetic fixtures; no network required |
| `src/review/` | offline or localhost-only review artifacts | unit tests plus human visual review |

## AI development lifecycle

AI work starts from an approved work ticket containing exactly one named host-test policy.
The Host runner selects policy from the default branch, creates an isolated worktree, and
retains Git metadata and GitHub writes. Codex may edit only the worktree paths allowed by
that immutable policy snapshot. The review package records base/head SHAs, changed files,
tests, manual checks, risks, and post-merge requirements.

See [safety boundaries](safety-boundaries.md), the
[work-ticket template](../plans/WORK-TICKET-TEMPLATE.md), and the
[review-package specification](../review/REVIEW-PACKAGE-SPEC.md).
