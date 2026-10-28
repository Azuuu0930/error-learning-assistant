"""実行せずに確認できる事実と候補を区別し、正常な名前を誤警告しない。"""

import pytest

from src.analyzer import analyze_error
from src.code_analysis import analyze_code
from src.parser import parse_python_traceback


def findings(code, kind):
    return [item for item in analyze_code(code).findings if item.kind == kind]


def test_undefined_name_includes_line_target_and_uncertainty():
    result = analyze_code("username = input()\nprint(user_name)")
    item = next(item for item in result.findings if item.kind == "undefined_name")
    assert (item.target, item.line, item.confidence) == ("user_name", 2, "medium")
    assert "候補" in item.message
    assert result.defined_names == ("username",)
    assert set(result.used_names) == {"input", "print", "user_name"}


def test_similar_defined_name_is_a_typo_candidate():
    item = findings("username = input()\nprint(user_name)", "similar_name")[0]
    assert item.related_names == ("username",)
    assert item.confidence == "medium"
    assert "タイプミスの可能性" in item.message


def test_weaker_similarity_is_low_confidence():
    item = findings("count = 3\nprint(coutn)", "similar_name")[0]
    assert item.related_names == ("count",)
    assert item.confidence == "low"


@pytest.mark.parametrize("code", ["print(score)\nscore = 100", "score = score + 100"])
def test_use_before_definition_including_assignment_rhs(code):
    item = findings(code, "use_before_definition")[0]
    assert (item.target, item.line, item.confidence) == ("score", 1, "high")


def test_local_builtin_shadow_has_different_rules_from_module():
    code = "def f():\n    print(len([1]))\n    len = 1"
    assert findings(code, "use_before_definition")[0].target == "len"
    assert not analyze_code("print(len([1]))\nlen = 1").findings


def test_function_local_is_not_visible_outside_function():
    code = "def f():\n    secret = 1\n    return secret\nprint(secret)"
    item = findings(code, "undefined_name")[0]
    assert (item.target, item.line) == ("secret", 4)


def test_class_attribute_is_not_a_bare_name_in_method():
    code = "class User:\n    age = 20\n    def get_age(self):\n        return age"
    item = findings(code, "undefined_name")[0]
    assert (item.target, item.line) == ("age", 4)


def test_comprehension_variable_does_not_leak():
    item = findings("values = [i for i in range(3)]\nprint(i)", "undefined_name")[0]
    assert (item.target, item.line) == ("i", 2)


def test_comprehension_inside_class_does_not_see_class_local_name():
    code = "class Example:\n    value = 1\n    values = [value for _ in range(3)]"
    assert findings(code, "undefined_name")[0].target == "value"


@pytest.mark.parametrize("code,module,imported,bound", [
    ("import math", "math", None, "math"),
    ("import math as m", "math", None, "m"),
    ("import os.path", "os.path", None, "os"),
    ("import os.path as p", "os.path", None, "p"),
    ("from math import sqrt as root", "math", "sqrt", "root"),
    ("from .helpers import load", ".helpers", "load", "load"),
])
def test_import_inventory_and_aliases(code, module, imported, bound):
    result = analyze_code(code)
    item = result.imports[0]
    assert (item.module, item.imported_name, item.bound_name, item.line) == (module, imported, bound, 1)
    assert bound in result.defined_names
    assert not result.findings


@pytest.mark.parametrize("target,code", [
    ("mathe", "import mathe as m"),
    ("some_pkg", "import some_pkg.tools"),
    ("some_pkg.tools", "from some_pkg import tools"),
])
def test_module_not_found_matches_correct_import(target, code):
    error = parse_python_traceback(f"ModuleNotFoundError: No module named '{target}'")
    result = analyze_code(code, error)
    item = next(item for item in result.findings if item.kind == "import_match")
    assert item.target == target and item.confidence == "high"
    assert "静的解析では確認できません" in item.message


def test_import_error_matches_original_name_even_with_alias():
    error = parse_python_traceback("ImportError: cannot import name 'square_root' from 'math'")
    result = analyze_code("from math import square_root as root", error)
    assert any(item.kind == "import_match" and item.target == "square_root" for item in result.findings)


def test_import_does_not_match_unrelated_module_or_wrong_line():
    error = parse_python_traceback("ImportError: cannot import name 'missing' from 'math'")
    assert not analyze_code("from csv import missing", error).findings
    error = parse_python_traceback('  File "main.py", line 2\nModuleNotFoundError: No module named \'mathe\'')
    assert not analyze_code("import mathe\nprint(1)", error).findings


def test_attribute_access_has_location_but_does_not_claim_missing_type_member():
    error = parse_python_traceback('  File "main.py", line 2\nAttributeError: \'str\' object has no attribute \'append\'')
    result = analyze_code('names = "Taro"\nnames.append("Hanako")', error)
    assert result.attributes[0].expression == "names.append"
    item = next(item for item in result.findings if item.kind == "attribute_access")
    assert (item.line, item.target, item.confidence) == (2, "append", "high")
    assert "実行時の値" in item.message
    assert "存在しません" not in item.message


def test_attribute_matching_filters_other_lines():
    error = parse_python_traceback('  File "main.py", line 3\nAttributeError: \'str\' object has no attribute \'append\'')
    result = analyze_code('names = "Taro"\nnames.append("A")\nnames.append("B")', error)
    assert [item.line for item in result.findings if item.kind == "attribute_access"] == [3]


@pytest.mark.parametrize("index", [3, 5, -4])
def test_obvious_index_error_from_list_literal(index):
    item = findings(f"items = [1, 2, 3]\nprint(items[{index}])", "index_out_of_range")[0]
    assert (item.line, item.confidence, item.related_names) == (2, "high", ("3", str(index)))
    assert "実行されれば" in item.message


@pytest.mark.parametrize("code", ["print([1, 2][2])", "items = (1, 2)\nprint(items[-3])", "items = []\nprint(items[0])", "items: list = [1]\nprint(items[2])"])
def test_direct_literal_tuple_empty_and_annotated_sequences(code):
    assert findings(code, "index_out_of_range")


@pytest.mark.parametrize("index", [0, 2, -1, -3])
def test_valid_negative_and_positive_indices_do_not_warn(index):
    assert not analyze_code(f"items = [1, 2, 3]\nprint(items[{index}])").findings


@pytest.mark.parametrize("code", [
    "items = [1, 2, 3]\nitems.append(4)\nprint(items[3])",
    "items = [1, 2, 3]\nalias = items\nalias.append(4)\nprint(items[3])",
    "items = [1, 2, 3]\nitems[:] = [1, 2, 3, 4]\nprint(items[3])",
    "items = [1, 2, 3]\nitems += [4]\nprint(items[3])",
    "items = [1, 2, 3]\ndef mutate():\n    items.append(4)\nmutate()\nprint(items[3])",
    "flag = True\nitems = [1, 2, 3]\nif flag:\n    items.append(4)\nprint(items[3])",
    "items = [1, 2, 3]\nfor _ in range(1):\n    items.append(4)\nprint(items[3])",
    "extra = [4,5]\nitems = [1, 2, 3, *extra]\nprint(items[4])",
    "items = [1, 2, 3]\nindex = int(input())\nprint(items[index])",
    "items = [1, 2, 3]\nprint(items[1:5])",
    "flag = True\nif flag:\n    items = [1]\nelse:\n    items = [1, 2]\n    print(items[1])",
    "items = [1, 2]\nclass Change:\n    items.append(3)\nprint(items[2])",
    "items = [1, 2]\nignored = [items.append(3) for _ in range(1)]\nprint(items[2])",
])
def test_do_not_infer_length_across_mutation_aliases_calls_or_branches(code):
    result = analyze_code(code)
    assert result.status == "parsed"
    assert not [item for item in result.findings if item.kind == "index_out_of_range"]


@pytest.mark.parametrize("code", [
    "x = 1\nprint(x, len([1,2]), str(x))",
    "import math as m\nfrom math import sqrt as root\nprint(m.pi, root(9))",
    "def f(value):\n    result = value + 1\n    return result\nprint(f(1))",
    "def f():\n    return score\nscore = 100\nprint(f())",
    "def outer():\n    def inner():\n        return score\n    score = 100\n    return inner()\nprint(outer())",
    "class User:\n    age = 20\n    def get_age(self):\n        return self.age\nprint(User().get_age())",
    "print([item * 2 for item in range(3)])",
    "print({item: item * 2 for item in range(3)})",
    "print({item for item in range(3)})",
    "print(sum(item for item in range(3)))",
    "print([(x,y) for x in range(2) for y in range(x)])",
    "print([[j for j in range(i)] for i in range(3)])",
    "i = 100\nvalues = [i for i in range(3)]\nprint(i)",
    "f = lambda value: value + 1\nprint(f(2))",
    "def listcomp():\n    value = (x := 1)\n    return x + value\nprint(listcomp())",
    "f, g = (lambda x: x + 1), (lambda y: y + 2)\nprint(f(1), g(1))",
    "a, b = (1,2)\nprint(a,b)",
    "for item in range(3):\n    print(item)",
    "from pathlib import Path\nwith Path('data.txt').open() as file:\n    print(file.read())",
    "try:\n    1 / 0\nexcept ZeroDivisionError as error:\n    print(error)",
    "values = [(last := item) for item in range(3)]\nprint(last)",
    "def set_score():\n    global score\n    score = 100\nset_score()\nprint(score)",
    "def outer():\n    value = 1\n    def inner():\n        nonlocal value\n        value += 1\n        return value\n    return inner()\nprint(outer())",
    "class User:\n    len = len([1])\nprint(User.len)",
    "print(__name__)",
    "data = {'x': 1}\nmatch data:\n    case {'x': value, **rest}:\n        print(value, rest)",
    "x: int\nx = 1\nprint(x)",
    "from __future__ import annotations\ndef f(x: Later) -> Later:\n    return x\nclass Later:\n    pass",
])
def test_normal_code_does_not_generate_false_warnings(code):
    result = analyze_code(code)
    assert result.status == "parsed", result.notes
    assert not result.findings


@pytest.mark.parametrize("code", ["if True\n    pass", "x = (", "\x00", "nonlocal x"])
def test_syntax_or_scope_errors_leave_log_analysis_working(code):
    result = analyze_error("SyntaxError: invalid syntax", code)
    assert result.code_analysis.status == "unavailable"
    assert result.code_analysis.notes
    assert result.error.error_type == "SyntaxError"
    assert result.explanation.summary
    assert result.hints == analyze_error("SyntaxError: invalid syntax").hints


@pytest.mark.parametrize("code", ["from unknown_module import *\nprint(provided_name)", "exec('x = 1')\nprint(x)"])
def test_dynamic_names_are_not_marked_as_definitely_undefined(code):
    result = analyze_code(code)
    assert result.status == "parsed" and result.notes
    assert not result.findings


def test_ast_analysis_does_not_execute_or_import_student_code(tmp_path):
    marker = tmp_path / "executed.txt"
    code = f"import surely_missing_module\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('bad')"
    assert analyze_code(code).status == "parsed"
    assert not marker.exists()


def test_no_code_preserves_original_result_and_hints():
    result = analyze_error("NameError: name 'user_name' is not defined")
    assert result.code_analysis is None
    assert "user_name" in result.hints[1]
    assert "行番号" in result.hints[0]


def test_ast_hints_reveal_similar_name_only_at_third_step():
    result = analyze_error("NameError: name 'user_name' is not defined", "username = input()\nprint(user_name)")
    assert "username" not in result.hints[0] + result.hints[1]
    assert "username" in result.hints[2] and "user_name" in result.hints[2]
    assert "可能性" in result.code_analysis.findings[1].message


def test_wrong_log_line_does_not_use_unrelated_ast_hint():
    log = '  File "main.py", line 99\nNameError: name \'user_name\' is not defined'
    result = analyze_error(log, "username = input()\nprint(user_name)")
    assert result.hints == analyze_error(log).hints


def test_large_input_and_excessive_nodes_are_skipped_without_crashing():
    assert analyze_code("#" * 100_001).status == "unavailable"
    assert analyze_code("items = [" + "0," * 20_001 + "]").status == "unavailable"


def test_findings_are_bounded_and_report_truncation():
    result = analyze_code("\n".join(f"print(missing_{i})" for i in range(60)))
    assert len(result.findings) == 50
    assert any("50件" in note for note in result.notes)
