# V3 delivery verification — 2026-10-28

The user requested completion of the interrupted diagnostics/UI delivery. This resume does not add AI/API functionality or change application, scoring, or dataset files.

## Fresh test run

From the project directory:

```powershell
../../work/.venv/Scripts/python.exe -B -X utf8 -m pytest tests evaluation/tests -q -p no:cacheprovider --basetemp=../../work/pytest-v3-resume-20261028-02 --tb=short
```

Result: **496 passed in 15.23s**, exit code 0 (422 application tests and 74 evaluator tests). The restricted-environment attempt stalled during Streamlit AppTest and was cancelled. The successful command ran in the usual process environment, as in the original Windows validation.

## Evidence integrity

- All 34 SHA-256 values in `freeze.json` match the current files.
- `evaluation/scoring.py` and all seven pre-existing v2 test files remain byte-identical to the preserved v2 snapshot.
- Recalculated metrics for all eight saved runs match their saved aggregates: v2/v3 with legacy/structured scoring, old holdout v2/v3, and normal corpus v2/v3.
- Each run's JSON and CSV contain matching case IDs and PASS/FAIL statuses.

This is an integrity check of saved evaluation results, not a fresh execution of the datasets. The original [evaluation report](REPORT.md), results and timestamps are preserved. No new manual browser test or student study was performed during this resume.

## Preserved outcomes and limits

- Structured 42-case evaluation: AST 33/36; Strict PASS 37/42; exception type 37/37; coverage 42/42.
- Legacy scoring: AST 25/36 and Strict PASS 28/42. The structured score gain includes recognition of evidence formats and new finding kinds; it is not solely new cause inference.
- Previously known holdout: 20/20 Strict PASS. This is a regression set, not a new blind holdout.
- New normal corpus from the original freeze: 29/30 PASS; one false positive (N-09) in both versions, retained as a control-flow limitation.
- No real-student learning-effect evidence is claimed.

The versioned delivery ZIP and its checksum manifest are saved alongside the earlier archives in `outputs/`. Earlier archives are preserved.
