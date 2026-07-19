# Epic #4 dependency graph

This document mirrors the current issue and default-branch policy relationships for
[Epic #4](https://github.com/Cheeky-Chap/tft-vision/issues/4). GitHub issue state remains the
source of truth; update this graph when dependencies change.

Status snapshot: 2026-07-19.

```text
#4 Epic: safe recognition and advisory system (open)
|
+-- #5 structured state and recognition foundation (merged/closed)
|
+-- #7 offline video ingestion foundation (merged/closed)
|    `-- #8 offline frame review gallery (merged/closed; explicitly depends on #7)
|         `-- #11 safe review-output documentation (merged/closed)
|
`-- #13 verifiable HUD OCR inspection (merged/closed)
     `-- #14 scene-change review and correction gallery (open; policy dependency on #13)
          `-- #15 ROI/grid calibration (open; policy dependencies on #13 and #14)
```

Solid sequencing above represents explicit issue text or default-branch shipping policy.
Merged foundations already present on `main` are prerequisites by repository history; they
must not be reopened or reimplemented in downstream tickets.

## Epic metadata alignment

Epic #4 should describe the configured merge flow as: Codex and Host gates pass, the Host
runner may register reviewed-head-matched GitHub native squash auto-merge, and GitHub
protection rules decide whether the PR merges. Neither Codex nor local Git performs a merge.
Manual Windows and visual verification occurs after GitHub confirms `MERGED`.
