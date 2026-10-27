"""Structured evidence and conservative boundaries of the v3 AST pass."""
from dataclasses import asdict
import json

import pytest

from src.code_analysis import analyze_code
from src.models import CodeAnalysis, CodeFinding


def finding(code, kind):
    result = analyze_code(code)
    assert result.status == 'parsed'
    return next(f for f in result.findings if f.kind == kind)


def test_structured_schema_is_backward_compatible_and_json_serializable():
    assert CodeFinding('example', 'message', 'high', 1).details == {}
    assert CodeAnalysis('parsed').facts == ()
    result = analyze_code('value = None\nvalue.missing')
    details = finding('value = None\nvalue.missing', 'missing_attribute').details
    assert details == {'exception_type': 'AttributeError', 'receiver_type': 'NoneType', 'attribute': 'missing'}
    json.dumps(asdict(result))


@pytest.mark.parametrize('code,kind,exception', [
    ('assert False', 'assertion_failure', 'AssertionError'),
    ('assert 0, "bad"', 'assertion_failure', 'AssertionError'),
    ('next(iter([]))', 'empty_iterator', 'StopIteration'),
    ('cursor = iter(())\nnext(cursor)', 'empty_iterator', 'StopIteration'),
    ('next(iter(range(0)))', 'empty_iterator', 'StopIteration'),
    ('data = {"a": 1}\nfor key in data:\n    data["b"] = 2', 'iteration_mutation', 'RuntimeError'),
    ('data = {"a": 1}\nfor key in data:\n    del data[key]', 'iteration_mutation', 'RuntimeError'),
    ('data = {1}\nfor item in data:\n    data.add(2)', 'iteration_mutation', 'RuntimeError'),
    ('data = {1}\nfor item in data:\n    data.remove(item)', 'iteration_mutation', 'RuntimeError'),
])
def test_new_definite_failures(code, kind, exception):
    item = finding(code, kind)
    assert item.details['exception_type'] == exception
    if kind == 'iteration_mutation':
        assert item.details['container_type'] in {'dict', 'set'}


@pytest.mark.parametrize('body,exception', [
    ('assert False', 'AssertionError'),
    ('next(iter([]))', 'StopIteration'),
    ('data = {1}\nfor item in data:\n    data.clear()', 'RuntimeError'),
])
def test_new_rules_use_exception_suppression(body, exception):
    code = 'try:\n' + '\n'.join('    ' + line for line in body.splitlines()) + f'\nexcept {exception}:\n    pass'
    result = analyze_code(code)
    assert not result.findings
    assert any(f.kind == 'handled_exception' and f.subject == exception for f in result.facts)


@pytest.mark.parametrize('code', [
    'assert True',
    'False and next(iter([]))',
    'if False:\n    assert False',
    'next(iter([]), None)',
    'next(iter([1]))',
    'next = lambda value: 1\nnext(iter([]))',
    'iter = lambda value: iter([1])\nnext(iter([]))',
    'cursor = iter([])\nunknown(cursor)\nnext(cursor)',
    'data = {"a": 1}\nfor key in data:\n    data["a"] = 2',
    'data = {"a": 1}\nfor key in data:\n    data["b"] = 2\n    break',
    'data = {1}\nfor item in data:\n    data.add(1)',
    'data = set()\nfor item in data:\n    data.add(1)',
    'data = {1}\nfor item in list(data):\n    data.clear()',
    'data = {1}\nfor item in data:\n    if input():\n        data.clear()',
    'data = {1}\nfor item in data:\n    unknown()\n    data.clear()',
    'data = {1}\nalias = data\nfor item in data:\n    data.clear()',
])
def test_new_rules_abstain_for_safe_or_unproven_paths(code):
    kinds = {f.kind for f in analyze_code(code).findings}
    assert not kinds & {'assertion_failure', 'empty_iterator', 'iteration_mutation'}


@pytest.mark.parametrize('code,kind', [
    ('def identity(value): return value\nidentity(None).strip()', 'missing_attribute'),
    ('def decorate(value): return "v=" + value\ndecorate(4)', 'incompatible_operation'),
    ('def echo(value):\n    saved = value\n    return saved\necho("a") + 2', 'incompatible_operation'),
    ('def echo(value="text"): return value\necho(value=None).strip()', 'missing_attribute'),
])
def test_bounded_pure_function_argument_and_return_propagation(code, kind):
    finding(code, kind)


@pytest.mark.parametrize('code', [
    'def identity(value):\n    unknown()\n    return value\nidentity(None).strip()',
    'def identity(value): return value\nidentity(unknown()).strip()',
    'def identity(value): return value\nidentity = unknown\nidentity(None).strip()',
    'def identity(value): return value\nunknown()\nidentity(None).strip()',
    'def f(value): return f(value)\nf(None).strip()',
    'def f(value):\n    global result\n    result = value\n    return value\nf(None).strip()',
])
def test_impure_or_unknown_function_calls_do_not_propagate(code):
    assert not any(f.kind == 'missing_attribute' for f in analyze_code(code).findings)


def test_simple_class_definite_attributes_and_missing_attribute_evidence():
    code = 'class Person:\n    def __init__(self, name):\n        self.name = name\nperson = Person("Ada")\nperson.nmae'
    result = analyze_code(code)
    item = next(f for f in result.findings if f.kind == 'missing_attribute')
    assert item.details['class_name'] == 'Person'
    assert item.details['receiver_type'] == 'Person'
    assert item.details['attribute'] == 'nmae'
    assert 'name' in item.details['defined_attributes']
    assert any(f.kind == 'defined_attribute' and f.subject == 'name' and f.details['class_name'] == 'Person' for f in result.facts)


@pytest.mark.parametrize('code', [
    'class Person:\n    def __init__(self):\n        self.name = "Ada"\nperson = Person()\nperson.name',
    'class Person:\n    def __getattr__(self, name): return 1\nperson = Person()\nperson.anything',
    'class Person(Base):\n    pass\nperson = Person()\nperson.anything',
    '@unknown\nclass Person:\n    pass\nperson = Person()\nperson.anything',
    'class Person:\n    def __init__(self):\n        setattr(self, "name", 1)\nperson = Person()\nperson.name',
    'class Person:\n    def __init__(self):\n        if input():\n            self.name = 1\nperson = Person()\nperson.name',
    'class Person:\n    pass\nperson = Person()\nunknown(person)\nperson.anything',
    'class Person:\n    pass\nperson = Person()\nperson.anything = 1\nperson.anything',
])
def test_classes_abstain_after_dynamic_or_unsupported_effects(code):
    assert not any(f.kind == 'missing_attribute' for f in analyze_code(code).findings)


@pytest.mark.parametrize('call,issue', [
    ('f()', 'missing'), ('f(1, 2)', 'too_many'),
    ('f(other=1)', 'unexpected_keyword'), ('f(1, value=2)', 'duplicate'),
])
def test_argument_details_distinguish_binding_problems(call, issue):
    item = finding('def f(value): return value\n' + call, 'call_arguments')
    assert item.details['argument_issue'] == issue
    assert item.details['required_count'] == 1
    assert item.details['supplied_count'] in {0, 1, 2}
    assert item.details['maximum_positional'] == 1


def test_builtin_facts_are_informational_and_respect_shadowing():
    result = analyze_code('len("abc")')
    assert not result.findings
    assert any(f.kind == 'builtin_reference' and f.subject == 'len' and f.line == 1 for f in result.facts)
    shadowed = analyze_code('len = lambda x: 1\nlen("abc")')
    assert not any(f.kind == 'builtin_reference' and f.subject == 'len' for f in shadowed.facts)


@pytest.mark.parametrize('code,expected', [
    ('"a" + 1', {'left_type': 'str', 'right_type': 'int', 'operator': '+'}),
    ('[1]["bad"]', {'receiver_type': 'list', 'index_type': 'str'}),
])
def test_existing_type_diagnostics_have_structured_details(code, expected):
    item = analyze_code(code).findings[0]
    assert all(item.details[key] == value for key, value in expected.items())


def test_iteration_failure_points_to_loop_advance_and_preserves_mutation_location():
    item = finding('data = {1}\nfor item in data:\n    data.clear()', 'iteration_mutation')
    assert item.line == 2
    assert item.details['mutation_line'] == 3


@pytest.mark.parametrize('code', [
    'class Box:\n    pass\nbox = Box()\nbox.__dict__["extra"] = 1\nbox.extra',
    'class Box:\n    pass\nbox = Box()\nvars(box)["extra"] = 1\nbox.extra',
    'class Box:\n    pass\nBox.extra = 1\nbox = Box()\nbox.extra',
    'class Box:\n    pass\nbox = Box()\nalias = box\nalias.extra = 1\nbox.extra',
    'class Box:\n    pass\nbox = Box()\nBox = unknown()\nbox.extra',
    'class Box:\n    pass\nbox = Box()\nbox.__init__()\nbox.extra',
    'def f(value): return value\nf.__defaults__ = ("safe",)\nf(None).extra',
    'def f(value): return value\nf(*unknown()).extra',
    'def f(value): return value\nf(**unknown()).extra',
    'def f(value): return value\nf(other=unknown()).extra',
    'cursor = iter([])\nalias = cursor\nunknown(alias)\nnext(cursor)',
    'data = {1}\nfor data in data:\n    data.clear()',
    'data = {1}\nfor item in data:\n    data.clear()\n    data.add(1)',
    'data = {1}\nfor item in data:\n    data.clear()\n    if True:\n        break',
    'data = {1}\nfor item in data:\n    data.clear()\n    raise RuntimeError()',
    'try:\n    next(iter([]))\nexcept UnknownError:\n    pass',
])
def test_metadata_and_new_rules_follow_existing_invalidation_and_control_boundaries(code):
    result = analyze_code(code)
    assert not any(f.kind in {'missing_attribute', 'empty_iterator', 'iteration_mutation'} for f in result.findings)


@pytest.mark.parametrize('body,exception', [
    ('assert False', 'AssertionError'),
    ('next(iter([]))', 'StopIteration'),
    ('data = {1}\nfor item in data:\n    data.clear()', 'RuntimeError'),
])
def test_unrelated_handlers_do_not_hide_new_failures(body, exception):
    code = 'try:\n' + '\n'.join('    ' + line for line in body.splitlines()) + '\nexcept ValueError:\n    pass'
    assert any(f.details.get('exception_type') == exception for f in analyze_code(code).findings)


def test_caught_pure_function_failures_and_return_values_are_isolated():
    result = analyze_code('def f(value): return "x" + value\ntry:\n    f(1)\nexcept TypeError:\n    pass')
    assert not result.findings
    assert any(f.kind == 'handled_exception' and f.subject == 'TypeError' for f in result.facts)


def test_repeated_pure_calls_do_not_reuse_first_argument_values():
    result = analyze_code('def echo(value): return value\nfirst = echo("text")\necho(None).strip()')
    assert [(f.line, f.details.get('receiver_type')) for f in result.findings if f.kind == 'missing_attribute'] == [(3, 'NoneType')]


def test_pure_function_summary_is_bounded():
    body = '\n'.join('    item = value' for _ in range(17))
    result = analyze_code('def f(value):\n' + body + '\n    return value\nf(None).extra')
    assert not any(f.kind == 'missing_attribute' for f in result.findings)


def test_new_hint_diagnostics_do_not_reveal_evidence_until_third_hint():
    from src.analyzer import analyze_error
    result = analyze_error('StopIteration:', 'next(iter([]))')
    assert '既知の空' not in ''.join(result.hints[:2])
    assert '既知の空' in result.hints[2]


@pytest.mark.parametrize('code', [
    'unknown()\nclass Box:\n    pass\nbox = Box()\nbox.extra',
    'class Box(metaclass=unknown):\n    pass\nbox = Box()\nbox.extra',
    'class Box(object):\n    pass\nbox = Box()\nbox.extra',
    'class Box:\n    def __init__(self, value):\n        self.value = value\nbox = Box(*unknown())\nbox.extra',
    'class Box:\n    def __init__(self, value):\n        self.value = value\nbox = Box(**unknown())\nbox.extra',
    'class Box:\n    def __init__(self, value):\n        self.value = value\nbox = Box()\nbox.extra',
    'class Box:\n    def __init__(self, value):\n        self.value = value\nbox = Box(1, 2)\nbox.extra',
    'class Box:\n    def __init__(self):\n        self.value = unknown()\nbox = Box()\nbox.extra',
    'class Box:\n    def __init__(self):\n        self.value = 1 + 2\nbox = Box()\nbox.extra',
    'class Box:\n    def __setattr__(self, name, value): pass\nbox = Box()\nbox.extra',
    'class Box:\n    def __init__(self):\n        self.__class__ = unknown\nbox = Box()\nbox.extra',
    'class Box:\n    @unknown\n    def __init__(self): pass\nbox = Box()\nbox.extra',
])
def test_class_summaries_fail_closed_on_construction_uncertainty(code):
    assert not any(f.kind == 'missing_attribute' for f in analyze_code(code).findings)


@pytest.mark.parametrize('code,absent_kind', [
    ('if input():\n    len("x")', 'builtin_reference'),
    ('with unknown():\n    assert False', 'handled_exception'),
    ('if input():\n    class Box:\n        def __init__(self):\n            self.value = 1', 'defined_attribute'),
    ('if False:\n    len("x")', 'builtin_reference'),
    ('try:\n    pass\nexcept Exception:\n    len("x")', 'builtin_reference'),
])
def test_facts_are_not_presented_as_observed_in_unproven_paths(code, absent_kind):
    # The condition/context expression on line 1 is genuinely evaluated.
    assert not any(f.kind == absent_kind and f.line > 1 for f in analyze_code(code).facts)


def test_serializing_all_new_diagnostics_contains_only_json_data():
    codes = ['assert False', 'next(iter([]))', 'data = {1}\nfor item in data:\n    data.clear()',
             'def echo(value): return value\necho(None).missing',
             'class Box:\n    def __init__(self):\n        self.value = 1\nBox().missing']
    for code in codes:
        assert json.loads(json.dumps(asdict(analyze_code(code))))['status'] == 'parsed'


def test_merging_different_instance_models_does_not_invent_missing_attributes():
    code = ('class Empty:\n    pass\nclass Named:\n    def __init__(self):\n        self.name = "Ada"\n'
            'if input():\n    value = Empty()\nelse:\n    value = Named()\nvalue.name')
    assert not any(f.kind == 'missing_attribute' for f in analyze_code(code).findings)


def test_iteration_mutation_abstains_for_values_with_possible_destructor_effects():
    code = 'data = {"a": unknown()}\nfor key in data:\n    data.clear()'
    assert not any(f.kind == 'iteration_mutation' for f in analyze_code(code).findings)
