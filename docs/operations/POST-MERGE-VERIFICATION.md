# Post-merge verification

Automated merge gates prove repository-level checks for one reviewed head. They do not prove
that a Windows capture environment, OCR installation, monitor layout, or visual output works.

## State model

```text
MERGED
  -> DEPLOYMENT_REQUIRED
  -> POST_MERGE_VERIFYING
  -> OPERATIONALLY_VERIFIED
```

| State | Meaning | Exit evidence |
| --- | --- | --- |
| `MERGED` | GitHub confirms merged status, timestamp, and merge commit | expected reviewed head is represented by the merge |
| `DEPLOYMENT_REQUIRED` | operator records whether a Windows checkout/tool update is required | target environment and expected merge SHA are identified, or deployment is explicitly not applicable |
| `POST_MERGE_VERIFYING` | operator is executing manual checks against the expected version | dated checklist with environment and artifact locations outside Git |
| `OPERATIONALLY_VERIFIED` | required checks passed on the intended environment | verifier, time, tested SHA/version, results, and remaining limitations |

A failed check remains in `POST_MERGE_VERIFYING` or transitions to a new corrective ticket.
It must not be relabeled as verified. Rollback means restoring the previously recorded
working version; it never means rewriting Git history.

## TFT Vision Windows checklist

1. Record the GitHub merge commit and the exact commit checked out on the Windows machine.
2. Confirm the virtual environment and documented dependencies without exposing `.env`.
3. Run CLI help and unit tests applicable to the merged change.
4. On a user-controlled TFT session, confirm monitor selection and game-region alignment.
5. Capture one user-initiated frame and inspect ROI boundaries at the expected resolution.
6. For OCR changes, use owned gold/level crops and record recognized value, status,
   confidence, raw-text visibility, and failure handling.
7. For review UI changes, inspect representative normal, dark, transition, low-quality, and
   missing/corrupt inputs. Confirm no remote assets are required.
8. Confirm outputs stay in ignored external paths and no capture/dataset artifact is staged.
9. Confirm the application emitted no synthetic clicks or keyboard input.

Do not commit screenshots or reports as evidence. Store them in an approved operational
location and link only a non-sensitive verification record.
