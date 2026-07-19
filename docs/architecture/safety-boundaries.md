# Safety boundaries

## Non-negotiable boundaries

- No automatic mouse clicks, keyboard input, purchases, sales, rerolls, leveling, or game
  control.
- No client modification, authentication bypass, anti-cheat bypass, or remote-control path.
- No captures, crops, screenshots, videos, datasets, labels, HTML reports, JSON review
  results, model files, or weights in Git.
- No `.env`, credentials, cookies, tokens, logs, sessions, or user-home paths in artifacts.
- No claim that Windows capture, OCR quality, or visual quality passed based on Linux tests.

## Automation authority

| Actor | May do | Must not do |
| --- | --- | --- |
| Codex | edit allowlisted worktree files; run fixed tests | fetch, branch, commit, push, merge, change PR metadata, operate a game |
| Host runner | preflight, worktree creation, tests, commit/push, PR/check management | admin bypass, direct main push, local main merge, force push, deployment |
| GitHub | enforce rules and complete configured native auto-merge | bypass required checks or reviewed-head matching |
| Human operator | approve scope, inspect PR, perform Windows/manual verification | commit runtime data or treat automated checks as visual proof |

## Merge boundary

The default-branch configuration enables squash auto-merge. Codex never enables, registers,
or performs a merge. The Host runner may register GitHub native auto-merge only after every
documented gate passes and with exact reviewed-head matching. GitHub rulesets and required
checks remain authoritative. A registered auto-merge request is not a completed merge.

## Fail-closed rules

Unknown, missing, duplicate, or malformed policy selectors stop the task. A changed head
invalidates host-test and review evidence. Out-of-scope files, runtime data, unresolved
blocking conversations, or absent manual evidence prevent operational verification.
