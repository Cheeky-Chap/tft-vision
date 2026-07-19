# Review package specification

Every AI-assisted PR must make the following evidence easy to verify.

## Required identity

- Repository and linked ticket/Epic
- Base branch and immutable base SHA
- Branch and full head SHA
- Named host-test policy and policy snapshot SHA
- Complete changed-file list

## Required scope evidence

- Allowed paths exercised
- Forbidden-path scan result
- Explicit statement that no captures, datasets, reports, weights, secrets, or runtime data
  are included
- Explicit statement that no automatic game input was added

## Required verification

- Exact fixed commands and exit codes
- Test count and result
- `git diff --check` result
- Platform limitations, especially Linux versus Windows capture/OCR verification
- Confirmed P0/P1 findings for the current head, if any
- Unresolved review conversations and remaining risks

## Merge and operations handoff

- Merge method and whether native auto-merge is merely eligible, registered, or completed
- Deployment requirement
- Manual verification checklist and expected evidence
- Rollback owner and trigger

Do not mark a review package complete when evidence belongs to an earlier head SHA.
