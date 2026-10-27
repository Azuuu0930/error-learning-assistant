"""新しい出力の対応を足しても、意味的な採点条件を変更しない。"""
import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from evaluation.evaluate import PROJECT, baseline_changed, evaluate_case
from evaluation.scoring import ACTIONABLE, check_detection, warning
from src.analyzer import analyze_error


def test_semantic_scoring_functions_remain_identical_to_baseline():
    baseline = PROJECT.parent / 'error-learning-assistant-baseline' / 'evaluation' / 'scoring.py'
    def functions(path):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(node, ast.FunctionDef)}
    assert functions(baseline) == functions(PROJECT / 'evaluation' / 'scoring.py')


@pytest.mark.parametrize('code', ['value = None\nvalue.strip()', 'a = 0\n5 / a',
                                 'def f(a): return a\nf()', 'data = {}\ndata["unknown"]'])
def test_new_diagnostics_count_as_warnings(code):
    result = asdict(analyze_error('', code))
    assert warning(result['code_analysis'])


def test_complete_type_diagnosis_is_credited_without_changing_criterion():
    output = asdict(analyze_error('', 'x = None\nx.upper()'))
    assert check_detection('NoneType に upper がない', output, ast_only=True)['matched']
    output['code_analysis']['findings'] = []
    assert not check_detection('NoneType に upper がない', output, ast_only=True)['matched']


def test_informational_notes_are_not_warnings():
    output = asdict(analyze_error('', 'try:\n    x = 1 / 0\nexcept ZeroDivisionError:\n    x = 0'))
    assert output['code_analysis']['notes']
    assert not warning(output['code_analysis'])


def test_original_four_warning_kinds_are_still_recognized():
    assert {'undefined_name', 'use_before_definition', 'possibly_unbound', 'index_out_of_range'} <= ACTIONABLE
