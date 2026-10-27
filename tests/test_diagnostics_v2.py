"""確実な静的診断と、断定してはいけない状況を分ける開発時回帰テスト。"""
import pytest

from src.analyzer import analyze_error
from src.code_analysis import analyze_code


def kinds(code):
    return {f.kind for f in analyze_code(code).findings}


@pytest.mark.parametrize('code,kind', [
    ('n = 4\n"value=" + n', 'incompatible_operation'),
    ('text = input()\ntext + 2', 'incompatible_operation'),
    ('value = None\nvalue.strip()', 'missing_attribute'),
    ('value = b"abc"\nvalue.uppercase()', 'missing_attribute'),
    ('points = [2, 4]\npoints[0.5]', 'invalid_index_type'),
    ('points = (2, 4)\npoints["first"]', 'invalid_index_type'),
    ('data = {"region": "west"}\ndata["year"]', 'missing_key'),
    ('data = {}\ndata[[1, 2]] = 5', 'unhashable_key'),
    ('denominator = 0\n4 / denominator', 'zero_division'),
    ('denominator = -0.0\n4 % denominator', 'zero_division'),
    ('value = int("not-a-number")', 'invalid_conversion'),
    ('x = [1]\nx > 2', 'incompatible_operation'),
    ('def combine(first, second): return first + second\ncombine(1)', 'call_arguments'),
    ('def greet(person): return person\ngreet("one", "two")', 'call_arguments'),
    ('def greet(person): return person\ngreet(other="one")', 'call_arguments'),
    ('def make():\n    if input():\n        answer = 1\n    return answer\nmake()', 'possibly_unbound'),
    ('for element in ():\n    product = element\nprint(product)', 'possibly_unbound'),
])
def test_directly_supported_problems(code, kind):
    assert kind in kinds(code)


@pytest.mark.parametrize('code', [
    'n = 4\nprint(n + 2.5)',
    'flag = True\nprint(flag + 2)',
    'print("a" + "b", b"a" + b"b", [1] + [2], (1,) + (2,))',
    'item = None\nitem = "valid"\nprint(item.upper())',
    'items = [1, 2]\nprint(items[True], items[-1], items[:3])',
    'entry = {"k": 1}\nprint(entry["k"])',
    'entry = {}\nentry["k"] = 1\nprint(entry["k"])',
    'entry = {}\nalias = entry\nalias["k"] = 1\nprint(entry["k"])',
    'entry = {}\nentry.update(k=1)\nprint(entry["k"])',
    'def change():\n    global x\n    x = "okay"\nx = 10\nchange()\nprint("value=" + x)',
    'def value(): return 0\n4 / value()',
    'def f(value, extra=2): return value + extra\nf(1)',
    'def f(*values): return values\nf(1, 2, 3)',
    'def f(**values): return values\nf(arbitrary=1)',
    'def f(a, /, **kw): return a\nf(1, a=2)',
    'def f(a, *, limit=2): return a\nf(1)',
    'def f(a, b): return a + b\nargs = (1, 2)\nf(*args)',
    'def f(a): return a\nkwargs = {"a": 1}\nf(**kwargs)',
    'def f(a): return a\nf = print\nf(1, 2)',
    'def decorate(f): return print\n@decorate\ndef f(a): return a\nf(1, 2)',
    'if False:\n    x = 1 / 0\nprint("finished")',
    'def unused():\n    return "wrong" + 1\nprint("finished")',
    'choice = bool(input())\nif choice:\n    x = 1\nelse:\n    x = 2\nprint(x)',
    'for item in []:\n    ignored = 1 / 0\nprint("finished")',
    'try:\n    x = 1 / 0\nexcept ZeroDivisionError:\n    x = 0\nprint(x)',
    'try:\n    x = {}["missing"]\nexcept KeyError:\n    x = 0\nprint(x)',
    'try:\n    x = "text" + 1\nexcept (ValueError, TypeError):\n    x = 0\nprint(x)',
    'try:\n    x = 1 / 0\nexcept Exception:\n    x = 0\nprint(x)',
    'try:\n    x = 1 / 0\nexcept:\n    x = 0\nprint(x)',
    'def f(value):\n    if value is None:\n        return ""\n    return value.upper()\nf("text")',
    'from math import sqrt\nprint(sqrt(4))',
    'input = lambda: 4\nprint(input() + 1)',
    'def f():\n    value = 0\n    def inner():\n        nonlocal value\n        value = 2\n    inner()\n    return 4 / value\nf()',
])
def test_safe_unknown_mutated_caught_or_unreachable_cases_do_not_warn(code):
    result = analyze_code(code)
    assert result.status == 'parsed'
    assert not result.findings, result.findings


def test_literal_attribute_diagnosis_contains_type_and_value_without_fix_guarantee():
    result = analyze_code('payload = None\npayload.upper()')
    finding = next(f for f in result.findings if f.kind == 'missing_attribute')
    assert 'NoneType' in finding.message and 'payload' in finding.message and 'upper' in finding.message
    assert finding.confidence == 'high'
    assert '必ず' not in finding.message


def test_input_result_explanation_is_bound_to_operation():
    result = analyze_code('text = input()\ntext + 7')
    finding = next(f for f in result.findings if f.kind == 'incompatible_operation')
    assert 'input' in finding.message and '文字列' in finding.message and '変換' in finding.message


def test_handled_error_is_information_not_warning():
    result = analyze_code('try:\n    x = 5 / 0\nexcept ZeroDivisionError:\n    x = 0\nprint(x)')
    assert not result.findings
    assert any('ZeroDivisionError' in note and 'except' in note for note in result.notes)


def test_branch_diagnostic_is_uncertain_and_identifies_path():
    result = analyze_code('condition = False\nif condition:\n    result = 5\nprint(result)')
    finding = next(f for f in result.findings if f.kind == 'possibly_unbound')
    assert finding.target == 'result' and finding.confidence == 'medium'
    assert '経路' in finding.message and '可能性' in finding.message


def test_wrong_exception_handler_does_not_hide_warning():
    assert 'zero_division' in kinds('try:\n    x = 4 / 0\nexcept ValueError:\n    x = 0')


@pytest.mark.parametrize('log,words', [
    ('RecursionError: maximum recursion depth exceeded', ('再帰', '終了条件')),
    ('StopIteration', ('イテレータ', 'next')),
    ('AssertionError: invalid', ('assert', '条件')),
    ('RuntimeError: dictionary changed size during iteration', ('辞書', '変更')),
    ('RuntimeError: Set changed size during iteration', ('set', '変更')),
    ("UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte", ('UTF-8', 'バイト')),
    ("UnboundLocalError: cannot access local variable 'counter' where it is not associated with a value", ('ローカル', '代入')),
])
def test_standard_exception_explanations(log, words):
    result = analyze_error(log)
    text = result.explanation.summary + result.explanation.cause + ''.join(result.explanation.checkpoints)
    assert all(word in text for word in words)
    assert '専用説明はまだありません' not in text
    assert len(result.hints) == 3


@pytest.mark.parametrize('log,code,words', [
    ("SyntaxError: expected ':'", 'if 2 > 1\n    pass', ('if', 'コロン')),
    ("SyntaxError: invalid syntax. Maybe you meant '==' or ':=' instead of '='?", 'if count = 3:\n    pass', ('条件式', '=', '可能性')),
    ("SyntaxError: '(' was never closed", 'print("x"', ('括弧', '可能性')),
    ('SyntaxError: unterminated string literal', 'x = "missing', ('文字列', '可能性')),
])
def test_specific_syntax_explanations(log, code, words):
    explanation = analyze_error(log, code).explanation
    assert all(word in explanation.summary + explanation.cause for word in words)


def test_custom_provider_is_not_overridden_by_syntax_context():
    from src.models import Explanation
    class Custom:
        def explain(self, error):
            return Explanation('custom', 'own cause', ('check',), 'tip')
    assert analyze_error("SyntaxError: expected ':'", 'if True\n pass', provider=Custom()).explanation.summary == 'custom'


@pytest.mark.parametrize('code', [
    'items = []\ninput() and items.append(1)\nitems[0]',
    'items = []\nf"{items.append(1)}"\nitems[0]',
    'items = []\nf = lambda a=items.append(1): None\nitems[0]',
    'x = "safe"\ntry:\n    x = 1\n    1 / 0\nexcept ZeroDivisionError:\n    x + 1',
    'for x in [1]:\n    break\nelse:\n    1 / 0',
    'assert True, 1 / 0',
    '1 > 2 < "x"',
    'class K:\n    def __len__(self):\n        global n\n        n = 2\n        return 1\nk = K()\nn = 0\nlen(k)\n1 / n',
    'def f():\n    yield 1\n    1 / 0\nf()',
    'items = []\ndef f(x: items.append(1)): pass\nitems[0]',
])
def test_review_side_effect_and_execution_order_regressions(code):
    assert not analyze_code(code).findings


def test_local_unbound_function_name_does_not_use_outer_signature():
    code = 'def g(a): pass\ndef f():\n    g()\n    g = lambda: None\nf()'
    result = analyze_code(code)
    assert any(f.kind == 'use_before_definition' and f.target == 'g' for f in result.findings)
    assert not any(f.kind == 'call_arguments' for f in result.findings)


@pytest.mark.parametrize('code', [
    'class K:\n    @property\n    def x(self):\n        global n\n        n = 2\n        return 1\nk = K()\nn = 0\nk.x\n1 / n',
    'class K:\n    def __getitem__(self, key):\n        global n\n        n = 2\n        return 1\nk = K()\nn = 0\nk[0]\n1 / n',
    'class K:\n    def __repr__(self):\n        global n\n        n = 2\n        return "x"\nk = K()\nn = 0\nprint([k])\n1 / n',
    'class K:\n    def __eq__(self, other):\n        global n\n        n = 2\n        return True\nk = K()\nn = 0\n[k] == [1]\n1 / n',
    'class K:\n    def __enter__(self):\n        global n\n        n = 2\n    def __exit__(self, *args): pass\nk = K()\nn = 0\nwith k:\n    1 / n',
    'try:\n    ZeroDivisionError = ZeroDivisionError\n    x = 1 / 0\nexcept ZeroDivisionError:\n    x = 0\nprint(x)',
    'for item in {}:\n    1 / 0',
])
def test_review_implicit_user_hooks_and_exception_aliases_are_conservative(code):
    assert not analyze_code(code).findings


def test_rebound_handler_does_not_suppress_unhandled_error():
    result = analyze_code('try:\n    TypeError = ValueError\n    "x" + 1\nexcept TypeError:\n    pass')
    assert any(f.kind == 'incompatible_operation' for f in result.findings)
    assert not any('捕捉・処理される経路' in n for n in result.notes)


def test_failing_assert_does_not_diagnose_following_expression():
    result = analyze_code('assert False\n"x" + 1')
    assert not any(f.kind == 'incompatible_operation' for f in result.findings)


def test_new_context_hints_reveal_diagnosis_only_at_third_step():
    result = analyze_error('  File "main.py", line 2\nTypeError: unsupported operand type(s) for +: \'str\' and \'int\'',
                           'quantity = 7\n"value=" + quantity')
    assert '不正な加算' not in result.hints[0] + result.hints[1]
    assert 'quantity' in result.hints[2] and '不正な加算' in result.hints[2]


@pytest.mark.parametrize('code', [
    'class K:\n    def __neg__(self):\n        global n\n        n = 2\n        return 1\nk = K()\nn = 0\n-k\n1 / n',
    'class K:\n    def __hash__(self):\n        global n\n        n = 2\n        return 1\nk = K()\nn = 0\n{k}\n1 / n',
    'class K:\n    def __index__(self):\n        global n\n        n = 2\n        return 0\nk = K()\nn = 0\n"abc"[k:]\n1 / n',
    'class K:\n    def __bool__(self):\n        global n\n        n = 2\n        return True\nk = K()\nn = 0\nassert k\n1 / n',
    'items = []\nx: items.append(1)\nitems[0]',
    'class C:\n    global input\n    input = lambda: 1\ntext = input()\ntext + 1',
    'def deco(f):\n    global n\n    n = 2\n    return f\nn = 0\n@deco\ndef f(): pass\n1 / n',
    'match 1:\n    case 1:\n        input = lambda: 1\ntext = input()\ntext + 1',
    'def f():\n    TypeError = ValueError\n    "x" + 1\ntry:\n    f()\nexcept TypeError:\n    pass',
])
def test_review_other_implicit_dispatches_are_not_assumed_pure(code):
    assert not analyze_code(code).findings


@pytest.mark.parametrize('code', [
    'def f(a, b): pass\nf(a=setattr(f, "__defaults__", (1, 2)))',
    'def f():\n    try:\n        1 / 0\n    finally:\n        return 1\nf()',
    'from contextlib import suppress\nwith suppress(TypeError):\n    "x" + 1',
])
def test_uncertain_signature_and_exception_escaping_do_not_warn(code):
    assert not analyze_code(code).findings


def test_known_endless_loop_does_not_diagnose_following_line():
    assert not analyze_code('while True:\n    pass\n"x" + 1').findings


@pytest.mark.parametrize('code', [
    'if TypeError == "TypeError":\n    1 / 0',
    'if input() == "":\n    1 / 0',
    'for item in range(0):\n    1 / 0',
    'def disabled(): return False\nwhile disabled():\n    1 / 0',
])
def test_unproven_branch_and_class_identity_do_not_create_literal_warnings(code):
    assert not analyze_code(code).findings
