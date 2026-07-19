# AI work ticket: concise title

Host test policy: exact-policy-id

## Problem

State the observable problem and why it matters. Link the Epic or ADR where applicable.

## Outcome

Describe verifiable user-visible or operator-visible behavior without prescribing arbitrary
shell commands.

## Allowed paths

- `path/**`

## Forbidden paths and actions

- runtime captures, crops, videos, datasets, labels, reports, and weights
- `.env`, credentials, logs, sessions, service control, deployment, and automatic game input
- `.github/codex-shipping.yml`, unless the ticket is an explicitly approved manual bootstrap
  or selects a higher-trust policy already present on its immutable base
- any path not allowed by the selected default-branch policy

## Acceptance criteria

- [ ] Functional or documentation outcome is observable.
- [ ] Unknown/unavailable states are not replaced by guesses.
- [ ] Required automated checks pass.
- [ ] Required manual checks are identified but not falsely claimed.
- [ ] No forbidden artifact is committed.

## Fixed verification

Reference the named policy's fixed commands. Do not put executable shell text in an issue
body; the Host runner executes only argv arrays from the trusted default-branch policy.

## Dependencies

- Repository/issue and required merged state, or `none`.

## Post-merge verification

- Deployment required: yes | no | operator decision
- Environment: Windows workstation | offline dataset | none
- Manual evidence required:
- Rollback condition:

## Review package notes

List expected risk areas, important files, and evidence reviewers should inspect.
