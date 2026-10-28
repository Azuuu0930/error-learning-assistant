from src.analyzer import analyze_error
from src.c_family import parse_c_family_diagnostic


def test_gcc_undeclared_identifier_includes_file_and_line():
    error = parse_c_family_diagnostic(
        "main.cpp:7:10: error: ‘total’ was not declared in this scope"
    )
    assert error.language == "cpp"
    assert (error.error_type, error.file, error.line, error.target) == (
        "CompilationError", "main.cpp", 7, "total"
    )
    assert error.category == "variable"


def test_gcc_diagnostic_without_column_is_supported():
    error = parse_c_family_diagnostic("main.c:3: error: expected ';' before 'return'", language="c")
    assert (error.file, error.line, error.category) == ("main.c", 3, "syntax")


def test_msvc_diagnostic_is_parsed():
    error = parse_c_family_diagnostic(
        "main.c(12,5): error C2065: 'count': undeclared identifier",
        language="c",
    )
    assert (error.language, error.file, error.line, error.target) == ("c", "main.c", 12, "count")


def test_missing_header_is_explained_as_compile_error():
    result = analyze_error(
        "main.cpp:1:10: fatal error: vectorz: No such file or directory",
        '#include <vectorz>', language="cpp",
    )
    assert result.error.category == "module"
    assert "ヘッダー" in result.explanation.summary
    assert result.code_context[0].is_error


def test_linker_and_runtime_diagnostics_are_distinguished():
    linker = analyze_error("undefined reference to `render()'", language="cpp")
    runtime = analyze_error("Segmentation fault (core dumped)", language="c")
    assert linker.error.error_type == "LinkerError"
    assert linker.error.category == "linker"
    assert "リンク" in linker.explanation.summary
    assert runtime.error.error_type == "SegmentationFault"
    assert runtime.error.category == "runtime"


def test_non_diagnostic_text_is_not_misclassified():
    error = parse_c_family_diagnostic("Building target main.cpp\nBuild succeeded")
    assert error.status == "unrecognized"
    assert error.error_type is None


def test_python_analysis_is_unchanged_when_language_is_selected():
    result = analyze_error("NameError: name 'missing' is not defined", "print(missing)")
    assert result.error.language == "python"
    assert result.code_analysis is not None
