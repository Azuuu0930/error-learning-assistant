# Diagnostics and Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Independent UI and backend domains may run concurrently.

**Goal:** Improve useful diagnoses with structured evidence and deliver a polished animated learning workspace.
**Architecture:** Extend existing AST passes; preserve legacy scoring alongside structured scoring. Use Streamlit widgets plus an isolated presentation layer.
**Tech Stack:** Python 3.12, ast/symtable, Streamlit 1.65, CSS, pytest.
**Spec:** ../specs/2026-10-27-diagnostics-and-experience-design.md

## Global Constraints
Preserve original 208 app tests and approved evaluator fixtures. No code execution in app, dataset-ID logic, artificial loading delay, or new remote service. Preserve earlier archives/results. Input100000 chars/AST20000 nodes. User chose navy/teal; other visual choices delegated.

## Review Focus
1. Implicit calls mutate supposedly known values: tests must invalidate facts.
2. Handled exceptions and break must not produce new fatal warnings.
3. Hint mode must not leak facts/details before hint3.
4. Catalog selection invalidates the previous result; keyboard and mobile remain usable.
5. Analysis exceptions remove skeleton and permit retry; HTML payloads remain inert.

## Task 1 — Structured and conservative diagnoses
Files: src/models.py, src/literal_analysis.py, src/code_analysis.py, src/hints.py, focused new helper modules, tests/test_diagnostics_v3.py.
Interface: exact CodeFinding.details, CodeFact, CodeAnalysis.facts in spec. Existing attributes remain compatible.
- [ ] Add failing positive/negative tests for facts, assert, next, mutations, pure functions, simple classes.
- [ ] Run tests red, implement bounded AST rules, run new and all original backend tests green.
- [ ] Report skipped constructs and review risks. No evaluation fixture reading or special cases.

## Task 2 — Animated Streamlit workspace
Files: app.py, src/ui.py, src/error_catalog.py, assets/, .streamlit/config.toml, tests/test_experience.py. Preserve src/view.py escaping contract if styling is changed.
Interface: analyze_error(log, source) unchanged. Preserve existing widget keys, hint stages, sample selection and invalidation callbacks.
- [ ] Add failing tests for catalog, selection/reset, processing failure/retry, motion preferences.
- [ ] Implement navy/teal layout, autocomplete, genuine skeleton, animations, reduced motion, empty/result states.
- [ ] Run AppTest plus original UI tests; root verifies browser/mobile separately.

## Task 3 — Structured evaluation and final validation
Files: evaluation/structured_scoring.py, evaluation/evaluate.py (opt-in --scoring), evaluation/tests/test_structured_scoring.py, evaluation/v3/, README.md, VERIFICATION.md.
- [ ] Test that fake prose/evidence or mismatched type/target cannot receive structured credit; legacy functions remain identical.
- [ ] Implement structured matching, preserving denominator and Strict PASS conditions, and optional new warning kinds. Legacy mode stays reproducible.
- [ ] Review backend/UI with independent reviewer, run all pytest with a fresh workspace basetemp (Windows elevation required for AppTest).
- [ ] Measure both versions with both scoring modes. Freeze app/scoring, then create and run new normal-code evaluation with primary-source provenance. Do not tune app afterward.
- [ ] Save all outcomes, document failure classifications/limits, capture UI screenshots, package current+baseline+v2 and verify ZIP bytes.

No Git repository exists, so no branch/worktree/commit steps apply. Test-first cycles and review findings serve as incremental checkpoints.
