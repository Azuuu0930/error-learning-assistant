"""採点の過大評価、失敗の握りつぶし、実行の停止を防ぐ評価器自身のテスト。"""
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from evaluation.evaluate import aggregate, baseline_changed, evaluate_case, expected_warn, load_dataset, PROJECT
from evaluation.runner import analyze_in_child, execute_code, execution_policy
from evaluation.scoring import check_detection, check_prohibited, warning
from src.analyzer import analyze_error


def pipeline(code, log=''):
    return asdict(analyze_error(log, code))


@pytest.mark.parametrize('code', [
    'import os\nos.remove("sample")',
    'import socket',
    'eval("print(1)")',
    'def f(): pass\nf = eval\nf("1")',
    'reader = open\nreader("other")',
    'open("../secret.txt")',
    'open("secret.txt", "w")',
    'open("CON")',
    'print((1).__class__)',
    'from math import __loader__',
    'from math import *',
])
def test_execution_rejects_unsafe_operations(code):
    assert execution_policy(code) is not None


def test_timeout_does_not_stop_next_execution():
    assert execute_code('while True:\n    pass\n', 0.3)['status'] == 'timeout'
    assert execute_code('print(1 + 2)\n', 5)['stdout'].strip() == '3'


def test_output_limit():
    assert execute_code('while True:\n    print("x" * 1000)\n', 5)['status'] == 'output_limit'


def test_recursion_is_observed_as_exception():
    result = execute_code('def recurse():\n    return recurse()\nrecurse()\n', 5)
    assert result['status'] == 'completed'
    assert result['exception_type'] == 'RecursionError'


def test_stdin_fixture_avoids_eof_error():
    result = execute_code('value = input()\nprint(value + 1)\n', 5)
    assert result['exception_type'] == 'TypeError'


def test_syntax_error_is_compile_failure():
    result = execute_code('if True\n    print(1)', 5)
    assert result['exception_type'] == 'SyntaxError'


def test_unknown_literal_method_is_not_a_typo_specific_allowlist():
    code = 'message = "hello"\nmessage.completely_unknown_method()\n'
    assert execution_policy(code) is None
    assert execute_code(code, 5)['exception_type'] == 'AttributeError'


def test_unknown_method_on_rebound_receiver_is_rejected():
    assert execution_policy('message = "hello"\nmessage = []\nmessage.completely_unknown_method()') is not None


def test_semantic_matching_uses_structured_target():
    output = pipeline('account = 10\nprint(accout)\n')
    assert check_detection('accout が未定義', output, ast_only=True)['matched']
    assert check_detection('類似候補 account', output, ast_only=True)['matched']
    assert not check_detection('missing が未定義', output, ast_only=True)['matched']


def test_later_definition_in_different_scope_is_not_credited():
    output = pipeline('print(total)\ndef calculate():\n    total = 5\n')
    # 明示的なfindingだけを足しても、別スコープの定義を結び付けてはいけない。
    output['code_analysis']['findings'] = [{'kind': 'use_before_definition', 'target': 'total', 'line': 1, 'message': '順序を確認'}]
    assert not check_detection('後続行で total が代入される', output, ast_only=True)['matched']


def test_argument_count_must_match_not_just_number_present():
    # 本体の新しい引数診断を混ぜず、評価器の数値照合そのものを検証する。
    output = pipeline('pass')
    output['explanation']['cause'] = 'multiply は3引数必要です。'
    assert not check_detection('multiply は2引数必要', output, ast_only=False)['matched']


def test_attribute_location_is_not_type_inference():
    output = pipeline('text = "hello"\ntext.nonexistent()\n', "AttributeError: 'str' object has no attribute 'nonexistent'")
    assert output['code_analysis']['findings'][0]['kind'] == 'attribute_access'
    output['code_analysis']['findings'] = [f for f in output['code_analysis']['findings'] if f['kind'] == 'attribute_access']
    assert not check_detection('str に nonexistent 属性がない', output, ast_only=True)['matched']


def test_none_attribute_expectation_is_mapped():
    output = pipeline('item = None\nitem.upper()\n')
    output['code_analysis']['findings'] = []  # 型の診断が返っていない観測だけを評価する。
    check = check_detection('NoneType に upper がない', output, ast_only=True)
    assert check['concept'] == 'missing_attribute'
    assert not check['matched']


def test_uncertain_similarity_is_not_certain_fix():
    output = pipeline('amount = 10\nprint(amont)\n')
    assert not check_prohibited('amount が確実な正解', output)['violated']
    output['code_analysis']['findings'][1]['message'] = 'amount が確実な正解です。'
    assert check_prohibited('amount が確実な正解', output)['violated']


def test_wrong_builtin_warning_is_counted_even_when_hedged():
    output = pipeline('print(len([]))')
    assert not check_prohibited('len が未定義', output)['violated']
    output['code_analysis']['findings'] = [{'kind': 'undefined_name', 'target': 'len', 'message': 'len は未定義の候補です。'}]
    assert check_prohibited('len が未定義', output)['violated']


def test_raw_source_and_example_are_not_diagnosis():
    output = pipeline('numbers = [1, 2]\nprint(numbers)')
    output['explanation']['fix_example'] = '辞書を走査中にサイズ変更'
    assert not check_detection('辞書を走査中にサイズ変更', output, ast_only=False)['matched']


def test_parse_unavailable_due_to_size_is_not_warning():
    assert not warning({'status': 'unavailable', 'notes': ['コードが10万文字を超えるため省略しました。']})
    assert warning({'status': 'unavailable', 'notes': ["expected ':'"]})


def test_unknown_expectation_is_not_silently_passed():
    check = check_detection('説明されていない新しい期待', pipeline('x = 1'), ast_only=True)
    assert check['status'] == 'unmapped'
    assert not check['matched']


def test_conflicting_should_warn_is_rejected():
    with pytest.raises(ValueError, match='conflicting'):
        expected_warn({'expected': {'execution': 'error', 'should_warn': True},
                       'analysis_expectations': {'should_warn': False}})


def test_json_and_jsonl_identical(tmp_path):
    case = {'id': 'arbitrary', 'code': 'print(1)', 'expected': {'execution': 'no_error', 'exception_type': None}}
    json_path = tmp_path / 'dataset.json'
    jsonl_path = tmp_path / 'dataset.jsonl'
    json_path.write_text(json.dumps({'num_cases': 1, 'cases': [case]}))
    jsonl_path.write_text(json.dumps(case) + '\n')
    assert load_dataset(json_path)[1] == load_dataset(jsonl_path)[1]


def test_case_id_and_title_do_not_affect_score():
    case = {'id': 'first', 'title': 'first title', 'difficulty': 'beginner', 'code': 'n = 1\nprint(missing)\n',
            'expected': {'execution': 'error', 'exception_type': 'NameError', 'should_warn': True},
            'analysis_expectations': {'should_detect': ['missing が未定義']}}
    first = evaluate_case(case, timeout=5, analysis_timeout=10)
    second = evaluate_case({**case, 'id': 'totally-different', 'title': 'different title'}, timeout=5, analysis_timeout=10)
    assert first['checks'] == second['checks']
    assert first['status'] == second['status']


def test_analysis_timeout_is_recorded():
    result = analyze_in_child(PROJECT, 'print(1)', '', 0.00001)
    assert result['status'] == 'timeout'


def test_crash_is_not_dropped_from_metric_denominator():
    normal_crash = {'expected': {'execution': 'no_error'}, 'actual': {'status': 'crashed'}, 'pass': False,
                    'checks': {'runtime_validated': True, 'error_type_correct': False, 'static_warning': None,
                               'static_warning_correct': False, 'log_assisted_warning_correct': False,
                               'ast_eligible': True, 'ast_diagnosis': [{'matched': False}],
                               'combined_diagnosis': [{'matched': False, 'status': 'missing'}], 'prohibited_claims': []}}
    result = aggregate([normal_crash])
    assert result['coverage']['numerator'] == 0
    assert result['coverage']['denominator'] == 1
    assert result['error_no_error_accuracy_static']['denominator'] == 1
    assert result['normal_cases_unevaluable'] == 1
    assert result['ast_diagnosis_accuracy']['percent'] == 0


def test_frozen_baseline_unchanged():
    manifest = json.loads((PROJECT / 'evaluation' / 'baseline_manifest.json').read_text(encoding='utf-8'))
    assert baseline_changed(manifest, PROJECT.parent / 'error-learning-assistant-baseline') == []
