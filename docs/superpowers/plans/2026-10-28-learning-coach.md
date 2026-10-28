# Learning coach implementation plan

> Implement with superpowers:executing-plans; root is the sole editor. Read-only final review by QA.

**Goal:** One bounded question after existing hints, optional AI selection with exact preview and safe fallback.
**Architecture:** Separate pure context/question module, provider/quotas module, and Streamlit panel. No parser/analyzer/scorer changes.
**Spec:** ../specs/2026-10-28-learning-coach-design.md

## Global constraints and review focus

No real student claims, no paid requests without setup, no raw code/log/name/value transmission, no automatic sends, no answer before existing reveal gate. Preserve historical evaluations. Watch identifiers hidden in details, stale consent on identical anonymous context, concurrent quota access, redirect credential leakage, and provider refusal.

## Tasks

- [x] Write failing tests in tests/test_learning_coach.py for allowlisting, 18 exception types, compatible selection, mismatched/extra response fields and fallback. Implement src/learning_coach.py and verify.
- [x] Write failing tests in tests/test_coach_provider.py for disabled/unauthorized/no-consent, strict Responses request, bad/oversized replies, timeout, redirect refusal, session/global/concurrent quotas. Implement src/coach_provider.py with fixed destination and no retry.
- [x] Write failing AppTests in tests/test_coach_ui.py: reveal gate, preview/no-send, explicit consent, successful selection/failure fallback, input/mode/goal invalidation, quota preserved on reset, no rerun sends. Implement src/coach_ui.py; minimally integrate app.py and update privacy copy.
- [x] Save empty research records and protocol plus honest submission brief/operator setup under docs/hackathon/. Update README and verification, preserving legacy claims as dated history.
- [x] Run all pytest and compare deterministic current outputs to saved reports. Read-only independent review; fix important issues with reproductions. Publish the tested default-off feature and standard guide, verify live fallback. Record real API and human-study limits.

## Execution record

- Starting point: df7c668, clean public main. Work on feat/hackathon-learning-coach.
- User delegated implementation choices and requested forward progress; no repeat design gate. Real interviews are consolidated into a human request packet.
- RED/GREEN: 58 unit/provider tests and 7 AppTests failed before implementation, then passed. Independent review found same-line wrong-target selection; 2 new failing tests reproduced it, local-only target matching fixed it.
- Final suite: 563 passed in 17.26s (original496 + new67). Current deterministic output equals stored output in all92cases; no snippets or real AI requests executed.
- Reviewer QA: no Important/Critical findings; AI reviewer grounding issue fixed with tests. API parameters/account access and selection quality remain unverified without operator setup.
- Ruling: keep AI default-off with required trial code and disclose that process quotas are not durable billing caps. Standard guides ship and remain usable without credentials; no paid smoke test or student-effect claim is fabricated.
- Published 77ecf04 via fast-forward to main. Live normal-mode NameError analysis, learning-goal panel and standard question displayed; AI correctly reported not configured. No external AI request occurred. The provided research packet remains unfilled.
