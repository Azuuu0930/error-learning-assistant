"""言語を明示した練習用ログとコード。実行はしない。"""
EXAMPLE_LABELS = {"name": "宣言した名前と使った名前が違う", "syntax": "文の終わりの記号が足りない", "link": "関数の定義が見つからない"}


def examples_for(language):
    c = language == "c"
    file = "main.c" if c else "main.cpp"
    main = "int main(void)" if c else "int main()"
    include = "#include <stdio.h>" if c else "#include <iostream>"
    output = 'printf("%d", totla);' if c else "std::cout << totla;"
    return {
        "name": (f"{file}:4:18: error: 'totla' undeclared identifier",
                 f"{include}\n{main} {{\n    int total = 3;\n    {output}\n    return 0;\n}}"),
        "syntax": (f"{file}:3:5: error: expected ';' before 'return'",
                   f"{main} {{\n    int total = 3\n    return total;\n}}"),
        "link": ("undefined reference to `calculate'",
                 f"int calculate(int value);\n{main} {{ return calculate(3); }}"),
    }
