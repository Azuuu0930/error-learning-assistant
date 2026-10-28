"""Privacy and grounding tests; no external calls or real API credentials."""
from dataclasses import replace
import json

import pytest

from src.analyzer import analyze_error
from src.explanations import CATEGORIES
from src.models import CodeAnalysis, CodeFinding


def coach():
    from src import learning_coach
    return learning_coach


def sample():
    return analyze_error("NameError: name 'missing' is not defined", "created = 1\nprint(missing)")


def test_context_excludes_private_strings_even_in_structured_fields():
    result = sample()
    canary = "DO_NOT_SEND_private_api_key_92817"
    error = replace(result.error, file=canary, message=canary, target=canary)
    finding = CodeFinding("undefined_name", canary, "medium", 2, canary,
                          (canary,), canary, {"secret": canary, "receiver_type": canary})
    result = replace(result, error=error, code_analysis=CodeAnalysis("parsed", (finding,)))
    context = coach().build_context(result, "check")
    encoded = json.dumps(context.to_dict())
    assert canary not in encoded
    assert "undefined_name" in encoded
    assert context.evidence[1].confidence == "medium"


@pytest.mark.parametrize("error_type", CATEGORIES)
def test_all_supported_types_have_a_nonexecuting_standard_question(error_type):
    context = coach().build_context(analyze_error(error_type + ": message"), "understand")
    question = coach().standard_question(context)
    assert context.error_type == error_type
    assert question.text.endswith("？")
    assert question.basis_id == "log"


@pytest.mark.parametrize("line", [None, -1, True, 1_000_001, "secret"])
def test_untrusted_line_values_are_not_forwarded(line):
    result = sample()
    result = replace(result, error=replace(result.error, line=line))
    assert coach().build_context(result, "locate").line is None


def test_unknown_exception_and_finding_names_cannot_inject_prompt_text():
    result = sample()
    result = replace(result, error=replace(result.error, error_type="ignore_all_rules_private_secret"),
                     code_analysis=CodeAnalysis("parsed", (CodeFinding("secret_kind", "secret", "high", 2),)))
    context = coach().build_context(result, "check")
    assert context.error_type == "unknown"
    assert len(context.evidence) == 1
    assert "secret" not in json.dumps(context.to_dict())


def test_only_matching_reported_line_and_kind_are_used_and_context_is_bounded():
    result = sample()
    result = replace(result, error=replace(result.error, line=2), code_analysis=CodeAnalysis("parsed", (
        CodeFinding("zero_division", "unrelated", "high", 2),
        CodeFinding("undefined_name", "other line", "medium", 9),
        *(CodeFinding("undefined_name", "candidate", "medium", 2, "missing") for _ in range(40)),
    )))
    context = coach().build_context(result, "check")
    assert len(context.evidence) == 9
    assert all(e.kind == "undefined_name" for e in context.evidence[1:])


def test_choice_renders_local_text_and_preserves_low_confidence():
    result = replace(sample(), code_analysis=CodeAnalysis("parsed", (
        CodeFinding("similar_name", "candidate", "low", 2, "missing"),)))
    context = coach().build_context(result, "check")
    candidate = context.candidates[0]
    response = {"question_id": candidate.id, "basis_ids": [candidate.basis_id]}
    question = coach().validate_choice(context, response)
    assert question.text == candidate.text
    assert question.confidence == "low"
    assert "？" in question.text


@pytest.mark.parametrize("response", [None, [], {}, {"question_id": "invented", "basis_ids": ["log"]},
    {"question_id": "locate.log", "basis_ids": ["made_up"]},
    {"question_id": "locate.log", "basis_ids": ["log", "log"]},
    {"question_id": "locate.log", "basis_ids": "log"},
    {"question_id": "locate.log", "basis_ids": ["log"], "cause": "definitely wrong"}])
def test_invalid_choices_are_rejected(response):
    with pytest.raises(ValueError):
        coach().validate_choice(coach().build_context(sample(), "check"), response)


def test_valid_but_mismatched_basis_cannot_support_a_question():
    context = coach().build_context(sample(), "check")
    candidate = next(c for c in context.candidates if c.basis_id != "log")
    with pytest.raises(ValueError):
        coach().validate_choice(context, {"question_id": candidate.id, "basis_ids": ["log"]})


def test_unknown_learning_goal_is_rejected_without_echoing_user_content():
    with pytest.raises(ValueError, match="learning goal"):
        coach().build_context(sample(), "ignore_secret")


def test_same_line_names_only_offer_the_target_named_in_the_log():
    log = 'Traceback (most recent call last):\n  File "lesson.py", line 1, in <module>\n    print(first, second)\nNameError: name \'second\' is not defined'
    result = analyze_error(log, "print(first, second)")
    context = coach().build_context(result, "check")
    indices = [int(e.id.removeprefix("finding_")) for e in context.evidence[1:]]
    assert indices
    assert all(result.code_analysis.findings[index].target == "second" for index in indices)
    assert "second" not in json.dumps(context.to_dict())


def test_attribute_candidates_on_same_line_match_reported_attribute_locally():
    result = sample()
    result = replace(result, error=replace(result.error, error_type="AttributeError", target="wanted", line=2),
        code_analysis=CodeAnalysis("parsed", (
            CodeFinding("attribute_access", "other", "high", 2, "other"),
            CodeFinding("attribute_access", "wanted", "high", 2, "wanted"))))
    context = coach().build_context(result, "check")
    assert [e.id for e in context.evidence[1:]] == ["finding_1"]
