import pytest

from src.analyzer import analyze_error
from src.classroom import build_card, encode_card, decode_card
from uuid import uuid4


@pytest.mark.parametrize('language', ['c', 'cpp'])
@pytest.mark.parametrize('log', ['Build succeeded', 'unrecognized text',
    "main.c:2: warning: unused variable 'count'", 'ERROR: AddressSanitizer: heap-buffer-overflow',
    "terminate called after throwing an instance of 'std::out_of_range'"])
def test_unknown_or_non_error_text_does_not_claim_compilation_failed(language, log):
    result = analyze_error(log, language=language)
    assert result.error.error_type is None
    assert '判断できません' in result.explanation.summary
    assert '作れませんでした' not in result.explanation.summary
    assert result.explanation.fix_example is None


@pytest.mark.parametrize('log', [
    "main.c:2: error: 'count' undeclared identifier",
    "main.c:2: fatal error: 'missing.h' file not found",
    "main.c:2: error: cannot convert a pointer",
])
def test_c_fixes_contain_no_cpp_syntax(log):
    result = analyze_error(log, language='c')
    assert result.explanation.fix_example
    assert 'iostream' not in result.explanation.fix_example
    assert 'std::' not in result.explanation.fix_example
    assert 'static_cast' not in result.explanation.fix_example


@pytest.mark.parametrize('level', ['error', 'エラー'])
@pytest.mark.parametrize('code,category', [('C2065', 'variable'), ('C2143', 'syntax'),
                                          ('C2440', 'type'), ('C1083', 'module')])
def test_msvc_code_handles_translated_messages_without_guessing_from_identifiers(level, code, category):
    result = analyze_error(f"main.c(12,5): {level} {code}: 診断の日本語本文", language='c')
    assert result.error.error_type == 'CompilationError'
    assert result.error.category == category
    assert result.error.diagnostic_code == code
    assert result.error.target is None
    card = build_card(result, card_id=str(uuid4()))
    assert decode_card(encode_card(card))['diagnostic_code'] == code


def test_msvc_linker_code_is_distinct_from_compile_code():
    result = analyze_error('main.obj : エラー LNK2019: 未解決の外部シンボル', language='cpp')
    assert result.error.error_type == 'LinkerError'
    assert result.error.diagnostic_code == 'LNK2019'
    assert 'リンク' in result.hints[0]
    assert '例外' not in ''.join(result.hints)


def test_unknown_msvc_code_stays_a_generic_compiler_diagnostic():
    result = analyze_error('main.c(2): error C9999: 未対応の内容', language='c')
    assert result.error.diagnostic_code == 'C9999'
    assert result.error.category == 'compile'


def test_japanese_warning_is_not_promoted_to_error():
    result = analyze_error('main.c(2): 警告 C2065: 警告のみ', language='c')
    assert result.error.error_type is None
    assert result.explanation.fix_example is None


@pytest.mark.parametrize('language,log', [('c', "main.c:2: error: expected ';'"),
                                       ('cpp', 'Segmentation fault')])
def test_c_family_hints_do_not_use_python_exception_instructions(language, log):
    result = analyze_error(log, language=language)
    assert '例外行' not in ''.join(result.hints)


def test_card_rejects_inconsistent_native_code_category():
    result = analyze_error('main.c(2): error C2065: undeclared identifier', language='c')
    value = build_card(result, card_id=str(uuid4()))
    value.update(category='type', concept_candidates=['types'])
    with pytest.raises(ValueError):
        encode_card(value)


@pytest.mark.parametrize('log', ['main.cpp(2): error LNK2005: symbol already defined',
                                'ld: symbol(s) not found for architecture arm64'])
def test_recognized_linker_formats_always_export_as_linker(log):
    result = analyze_error(log, language='cpp')
    assert result.error.error_type == 'LinkerError'
    assert result.error.category == 'linker'
    assert build_card(result, card_id=str(uuid4()))['phase'] == 'link'


@pytest.mark.parametrize('log', [
    'main.c:1:2: warning: #warning undefined symbol [-Wcpp]',
    'ld: warning: undefined symbol: _foo',
    'main.c:1:2: warning: possible segmentation fault',
    'note: undefined reference to render',
    '警告: access violation の可能性',
    '  warning: undefined symbol: _foo',
    '\tnote: undefined reference to render',
])
def test_warning_and_note_lines_are_not_reinterpreted_as_runtime_or_link_failure(log):
    result = analyze_error(log, language='c')
    assert result.error.error_type is None
    assert result.explanation.fix_example is None
