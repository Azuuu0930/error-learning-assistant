# Hackathon learning coach — bounded vertical slice

The user requested autonomous team improvements for the November 7 submission, with real-world research consolidated as requests rather than blocking development. This executes the previously recommended grounded AI support direction. Only the root implements; three read-only advisers cover AI, learner research and QA.

## Scope and choices

Keep Python/Streamlit, the deployed navy/teal UI, parser/AST, explanations, scoring and three existing hints. Add one optional next-step coach after hint 3 (or normal mode). The learner selects a fixed learning goal and receives one question and a locally displayed evidence reference. No chat, free-form learner answer, execution or automatic repair.

Two approaches considered: free-form AI rephrasing versus AI selection from reviewed questions. Use the latter: arbitrary prose with valid citation IDs still cannot be reliably checked for invented claims. AI ranks compatible questions from the evidence and learner goal; the app validates and renders local text. Its added educational value over deterministic selection is a hypothesis to test, not an established result.

## Data boundary

Build an explicit allowlist: known exception type, finding kind/confidence, valid line number, static question candidates, fixed goal. Never serialize dataclasses, raw traceback/code, paths, names, values, messages, evidence strings, related names, free-form details or user answers. Show the exact JSON request before opt-in; credentials travel only in the HTTPS authorization header to the fixed OpenAI Responses endpoint. Select the documented `gpt-5.4-mini-2026-03-17` snapshot, no reasoning, 256 output tokens, store=false. This is not a promise of zero provider retention; link the provider policy.

The response can only select a supplied question ID and one of its matching evidence IDs. Reject extra fields, unknown/mismatched IDs, refusal/incomplete/oversized/malformed replies. Preserve confidence and locally show the original finding only after the existing reveal gate.

## Operations and failure

Default off. Operator configures an API key, explicit enable flag and trial access code (at least 16 characters) in ignored Streamlit Secrets. No browser API-key entry. Consent and trial code required before a paid request. One attempt per explicit click, 10-second socket timeout, no retries, 64KB response bound. A locked shared service caps attempts at 3/session and 30/process per rolling 24 hours and admits only one active request; failures count too. These in-memory guards reset on process restart and are not a durable spending cap. Operator must manage project billing/limits and rotate the trial code; no automatic paid smoke test in this task without credentials and authorization.

Disabled service and failures fall back to a clearly labeled deterministic guide. Do not cache student content across users or show/log provider exceptions. Clear preview/consent/output/trial code on input, reanalysis, sample/catalog, mode or goal changes; preserve session identity for quotas. No request on a Streamlit rerun or motion preference change.

## Evidence and acceptance

Keep the original 496 tests; add privacy canaries, validation/transport/quota and AppTest consent/reset/reveal/fallback coverage. Recheck current deterministic outputs against the saved 42-case/20-case/30-normal reports without executing user code or rewriting historical results. Prepare a task protocol, empty anonymous CSV and evidence-based submission brief. Student study and real API selection quality remain unverified until actually performed.
