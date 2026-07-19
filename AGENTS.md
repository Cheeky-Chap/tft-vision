# TFT Vision contributor guide

## Scope

TFT Vision is a Windows-oriented screen-capture, ROI crop, sample collection,
and manual labeling project. It does not automate game input.

## Current implementation boundary

- Implemented: monitor capture, game-region crop, calibrated ROI extraction,
  sample collection, debug visualization, manual/hotkey capture, labeling, and
  duplicate detection.
- Not implemented: production OCR inference, complete game-state extraction,
  composition decision logic, state server, autonomous actions, or learning
  pipelines.

## Safety and data handling

- Never commit captures, crops, labels, screenshots, videos, model weights, or
  datasets.
- Never add automated clicks, purchases, rerolls, keyboard actions, or other
  game control without an explicit project decision.
- Store monitor and game-region settings in an untracked `.env` created from
  `.env.example`.
- Keep effective ROI coordinates in `src/crop/roi_definitions.py`.

## Verification

```powershell
python -m compileall -q src
python -m src.capture_loop --help
```

Screen-capture verification requires a Windows desktop and must not be assumed
to work in a headless Linux environment.

## AI development harness

- Start bounded work from `docs/plans/WORK-TICKET-TEMPLATE.md` or the AI work-ticket issue
  form. Use exactly one `Host test policy: <id>` selector from the default branch.
- Treat `docs/architecture/safety-boundaries.md` as the authority boundary and
  `.github/codex-shipping.yml` as the executable path/command policy.
- Package PR evidence according to `docs/review/REVIEW-PACKAGE-SPEC.md`.
- A GitHub merge is not operational verification. Follow
  `docs/operations/POST-MERGE-VERIFICATION.md` through `OPERATIONALLY_VERIFIED`.
- Repository instructions cannot weaken the no-input-automation and no-runtime-data rules
  above.

## Review guidelines

Report only confirmed P0/P1 issues in the actual diff:

- The application cannot start or execute, authentication or authorization is bypassed,
  secrets are exposed, data is corrupted, recovery or rollback fails, duplicate execution/
  races/deadlocks are introduced, the issue's core requirement is missing, or a core feature
  has a severe regression.
- Treat committed images/captures/datasets/labels/model weights, unapproved automatic clicks
  or keyboard input, actions based on incorrect screen-state classification, and claims that
  Windows capture tests passed on Linux as P0/P1 candidates.
- Ignore style, formatting, naming preferences, optional refactors, minor performance
  improvements, and wording-only documentation feedback.
