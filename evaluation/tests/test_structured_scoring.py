"""Structured observations must agree with the requested subject; raw code is not a diagnosis."""
import ast
import copy
import json
from pathlib import Path

import pytest


def matcher():
    from evaluation.structured_scoring import check_detection
    return check_detection


def output(kind=None, details=None, target=None, facts=()):
    findings = [] if kind is None else [{'kind': kind, 'target': target, 'line': 3,
        'message': '観測した問題', 'confidence': 'high', 'related_names': [],
        'evidence': 'raw code is never sufficient', 'details': details or {}}]
    return {'code_analysis': {'status': 'parsed', 'findings': findings, 'facts': list(facts),
                              'notes': [], 'definitions': [], 'uses': [], 'imports': []},
            'explanation': {}, 'hints': []}


@pytest.mark.parametrize('expectation,kind,details,target', [
    ('run の定義より多い位置引数', 'call_arguments', {'argument_issue': 'too_many', 'maximum_positional': 1, 'supplied_count': 3}, 'run'),
    ('2引数必要', 'call_arguments', {'argument_issue': 'missing', 'required_count': 2, 'supplied_count': 1}, 'calculate'),
    ('1引数しか渡していない', 'call_arguments', {'argument_issue': 'missing', 'required_count': 2, 'supplied_count': 1}, 'calculate'),
    ('render に color 引数が定義されていない', 'call_arguments', {'argument_issue': 'unexpected_keyword', 'keyword': 'color'}, 'render'),
    ('bytes と str の混在', 'incompatible_operation', {'operator': '+', 'left_type': 'bytes', 'right_type': 'str'}, None),
    ('list に push がない', 'missing_attribute', {'receiver_type': 'list', 'attribute': 'push'}, 'push'),
    ('0で除算', 'zero_division', {'exception_type': 'ZeroDivisionError'}, None),
    ('assert の条件が False', 'assertion_failure', {'exception_type': 'AssertionError'}, None),
    ('空のイテレータにnext', 'empty_iterator', {'exception_type': 'StopIteration'}, None),
    ('辞書の走査中のサイズ変更', 'iteration_mutation', {'exception_type': 'RuntimeError', 'container_type': 'dict'}, None),
    ('set の走査中のサイズ変更', 'iteration_mutation', {'exception_type': 'RuntimeError', 'container_type': 'set'}, None),
])
def test_structured_evidence_credits_observed_relationship(expectation, kind, details, target):
    result = matcher()(expectation, output(kind, details, target), ast_only=True)
    assert result['matched'] and result['evidence']
    assert result['evidence_source'] == 'structured'


@pytest.mark.parametrize('expectation,facts', [
    ('print と len は builtins', [{'kind': 'builtin_reference', 'subject': n, 'line': 1, 'details': {}} for n in ('len', 'print')]),
    ('TypeError は except で処理', [{'kind': 'handled_exception', 'subject': 'TypeError', 'line': 2, 'details': {}}]),
    ('name 属性は存在', [{'kind': 'defined_attribute', 'subject': 'name', 'line': 2, 'details': {'class_name': 'Account'}}]),
])
def test_information_facts_credit_explanation_without_becoming_warnings(expectation, facts):
    from evaluation.structured_scoring import warning
    p = output(facts=facts)
    assert matcher()(expectation, p, ast_only=True)['matched']
    assert not warning(p['code_analysis'])


@pytest.mark.parametrize('expectation,kind,details,target,facts', [
    ('run の定義より多い位置引数', 'call_arguments', {'argument_issue': 'too_many', 'maximum_positional': 3, 'supplied_count': 1}, 'run', ()),
    ('run の定義より多い位置引数', 'call_arguments', {'argument_issue': 'too_many', 'maximum_positional': 1, 'supplied_count': 3}, 'other', ()),
    ('2引数必要', 'call_arguments', {'argument_issue': 'missing', 'required_count': 3, 'supplied_count': 1}, 'calculate', ()),
    ('bytes と str の混在', 'incompatible_operation', {'operator': '+', 'left_type': 'int', 'right_type': 'str'}, None, ()),
    ('list に push がない', 'attribute_access', {'receiver_type': 'list', 'attribute': 'push'}, 'push', ()),
    ('list に push がない', 'missing_attribute', {'receiver_type': 'str', 'attribute': 'push'}, 'push', ()),
    ('print と len は builtins', None, {}, None, ({'kind': 'builtin_reference', 'subject': 'print', 'line': 1, 'details': {}},)),
    ('TypeError は except で処理', None, {}, None, ({'kind': 'handled_exception', 'subject': 'ValueError', 'line': 1, 'details': {}},)),
    ('name 属性は存在', None, {}, None, ({'kind': 'defined_attribute', 'subject': 'age', 'line': 1, 'details': {}},)),
    ('辞書の走査中のサイズ変更', 'iteration_mutation', {'exception_type': 'RuntimeError', 'container_type': 'set'}, None, ()),
])
def test_wrong_type_target_count_or_information_cannot_receive_credit(expectation, kind, details, target, facts):
    assert not matcher()(expectation, output(kind, details, target, facts), ast_only=True)['matched']


def test_raw_evidence_and_input_text_cannot_invent_a_structured_observation():
    p = output('attribute_access', {}, 'upper')
    p['code_analysis']['findings'][0]['evidence'] = 'NoneType に upper がない'
    p['code_context'] = [{'text': 'NoneType に upper がない'}]
    assert not matcher()('NoneType に upper がない', p, ast_only=True)['matched']


def test_matching_does_not_mutate_observations_or_depend_on_ids():
    p = output('zero_division', {'exception_type': 'ZeroDivisionError'})
    original = copy.deepcopy(p)
    result = matcher()('0で除算', p, ast_only=True)
    p['id'], p['title'] = 'irrelevant-new-id', 'unrelated'
    assert matcher()('0で除算', p, ast_only=True) == result
    del p['id'], p['title']
    assert p == original
    json.dumps(result)


def test_new_warning_kinds_are_actionable_but_legacy_scoring_is_preserved():
    from evaluation.structured_scoring import warning
    from evaluation.scoring import warning as legacy_warning
    for kind in ('assertion_failure', 'empty_iterator', 'iteration_mutation'):
        analysis = output(kind)['code_analysis']
        assert warning(analysis)
        assert not legacy_warning(analysis)


def test_scoring_cli_has_explicit_legacy_and_structured_modes():
    import inspect
    from evaluation.evaluate import evaluate_case
    assert inspect.signature(evaluate_case).parameters['scoring'].default == 'legacy'


def test_legacy_semantic_functions_are_byte_identical_to_v2():
    project = Path(__file__).resolve().parents[2]
    assert (project / 'evaluation/scoring.py').read_bytes() == (project.parent / 'error-learning-assistant-v2/evaluation/scoring.py').read_bytes()


@pytest.mark.parametrize('expectation', [
    'int と str の不正な加算', 'payload の bytes と str の混在',
    'payload の不正な加算',
])
def test_operation_evidence_must_match_requested_types_and_named_operands(expectation):
    p = output('incompatible_operation', {'operator': '+', 'left_type': 'bytes', 'right_type': 'str'})
    assert not matcher()(expectation, p, ast_only=True)['matched']
