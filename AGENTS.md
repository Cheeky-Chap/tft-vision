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
