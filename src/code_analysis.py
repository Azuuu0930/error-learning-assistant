"""ASTと標準symtableでコード文脈を調べる。コードの実行・importは行わない。

symtableは名前のスコープ判定だけに使う。実行順序は単純な文の範囲に限定し、
分岐や未知の呼び出しを越えてリストの長さを推測しない。
"""

import ast
import builtins
from dataclasses import dataclass, field
from difflib import get_close_matches, SequenceMatcher
from functools import cached_property
import re
import symtable

from src.models import (
    AttributeAccess, CodeAnalysis, CodeFinding, ImportInfo, NameDefinition, NameUse,
    ParsedError,
)
from src.literal_analysis import analyze_literals


CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}
_BUILTINS = set(dir(builtins))
_MODULE_NAMES = {"__name__", "__file__", "__package__", "__doc__", "__builtins__",
                 "__spec__", "__loader__", "__cached__", "__annotations__"}
_MAX_FINDINGS = 50


@dataclass
class _Scope:
    table: symtable.SymbolTable
    parent: "_Scope | None" = None
    deferred: bool = False
    bound: set[str] = field(default_factory=set)
    lengths: dict[str, int] = field(default_factory=dict)
    synthetic_names: set[str] | None = None
    synthetic_label: str | None = None
    is_comprehension: bool = False

    @property
    def label(self) -> str:
        return self.synthetic_label or f"{self.table.get_name()}@{self.table.get_lineno()}"

    @cached_property
    def names(self) -> set[str]:
        if self.synthetic_names is not None:
            return self.synthetic_names
        return {symbol.get_name() for symbol in self.table.get_symbols()
                if symbol.is_assigned() or symbol.is_imported() or symbol.is_parameter() or symbol.is_namespace()}


class _CodeVisitor(ast.NodeVisitor):
    def __init__(self, code: str, tree: ast.Module, table: symtable.SymbolTable):
        self.code = code
        self.root = _Scope(table, bound=set(_MODULE_NAMES))
        self.scope = self.root
        self.definitions: list[NameDefinition] = []
        self.uses: list[NameUse] = []
        self.imports: list[ImportInfo] = []
        self.attributes: list[AttributeAccess] = []
        self.findings: list[CodeFinding] = []
        self.notes: list[str] = []
        self._seen: set[tuple] = set()
        self._children_used: set[int] = set()
        # 動的に作る名前やimport *の提供名は分からないため、未定義を断定しない。
        self.dynamic_names = any(
            (isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names))
            or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"exec", "eval", "globals", "locals"})
            for node in ast.walk(tree)
        )
        if self.dynamic_names:
            self.notes.append("import * や動的な名前空間操作があるため、未定義名の候補検出を控えています。")
        self.remote_globals: set[str] = set()
        pending = list(table.get_children())
        while pending:
            child = pending.pop()
            self.remote_globals.update(symbol.get_name() for symbol in child.get_symbols()
                                       if symbol.is_global() and symbol.is_assigned())
            pending.extend(child.get_children())

    def _evidence(self, node: ast.AST) -> str:
        return (ast.get_source_segment(self.code, node) or "")[:240]

    def _add(self, finding: CodeFinding) -> None:
        key = (finding.kind, finding.line, finding.target)
        if key not in self._seen:
            self._seen.add(key)
            if len(self.findings) < _MAX_FINDINGS:
                self.findings.append(finding)
            elif not self.notes or "50件" not in self.notes[-1]:
                self.notes.append("表示する補助情報は先頭50件までに制限しています。")

    def _bind(self, name: str, line: int, kind: str = "assignment") -> None:
        self.scope.bound.add(name)
        self.scope.lengths.pop(name, None)
        self.definitions.append(NameDefinition(name, line, self.scope.label, kind))

    def _outer_names(self, scope: _Scope | None = None) -> set[str]:
        scope = scope or self.scope
        names = set(_BUILTINS) | _MODULE_NAMES
        parent = scope.parent
        while parent:
            # メソッドからクラス本体の名前を裸の変数としては参照できない。
            if parent.table.get_type() != "class":
                names.update(parent.names if scope.deferred else parent.bound)
            parent = parent.parent
        return names

    def _visible_names(self) -> set[str]:
        names = self.scope.bound - _MODULE_NAMES
        parent = self.scope.parent
        while parent:
            if parent.table.get_type() != "class":
                names = names | (parent.names if self.scope.deferred else parent.bound)
            parent = parent.parent
        return names - _MODULE_NAMES

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._bind(node.id, node.lineno)
            return
        if isinstance(node.ctx, ast.Del):
            self.scope.bound.discard(node.id)
            self.scope.lengths.clear()
            return
        self.uses.append(NameUse(node.id, node.lineno, self.scope.label))
        if node.id in self.scope.bound:
            return
        # Python 3.12+でinliningされた内包表記にも、独立した束縛を持たせる。
        scope = self.scope
        while scope.synthetic_names is not None and node.id not in scope.names:
            scope = scope.parent
            if scope.table.get_type() == "class" and scope.synthetic_names is None:
                scope = scope.parent
        symbol = scope.table.lookup(node.id) if node.id in scope.table.get_identifiers() else None
        local = node.id in scope.names
        if node.id in scope.bound:
            return
        # 関数のglobal/free名は、関数定義の後に代入される場合も有効。
        if scope is not self.root and symbol and (symbol.is_global() or symbol.is_free()) and not (scope.synthetic_names is not None and local):
            if node.id in self._outer_names(scope):
                return
        elif scope.table.get_type() == "class" and node.id in self._outer_names(scope):
            return
        elif (not local or scope is self.root) and node.id in _BUILTINS:
            return
        if node.id in self.remote_globals and (scope is self.root or (symbol and symbol.is_global())):
            return  # 関数呼び出しによるglobalの代入順序は、この解析では判定しない。
        if self.dynamic_names:
            return
        prior = any(item.name == node.id and item.scope == scope.label for item in self.definitions)
        if local and not prior:
            self._add(CodeFinding(
                "use_before_definition",
                f"「{node.id}」にはこのスコープ内に定義がありますが、{node.lineno}行目の参照までには値を与える処理が見つかりません。使用と定義の順序を確認してください。",
                "high", node.lineno, node.id, evidence=self._evidence(node),
            ))
        elif local:
            self._add(CodeFinding(
                "possibly_unbound",
                f"「{node.id}」は以前に定義されていますが、削除などにより{node.lineno}行目で値がない可能性があります。",
                "medium", node.lineno, node.id, evidence=self._evidence(node),
            ))
        else:
            self._add(CodeFinding(
                "undefined_name",
                f"「{node.id}」を使っていますが、このスコープから参照できる定義が貼り付けたコードには見つかりません。未定義名の候補です。",
                "medium", node.lineno, node.id, evidence=self._evidence(node),
            ))
            if 3 <= len(node.id) <= 80:
                candidates = sorted(name for name in self._visible_names() if 3 <= len(name) <= 80)[:200]
                similar = tuple(get_close_matches(node.id, candidates, n=3, cutoff=0.75))
                if similar:
                    confidence = "medium" if SequenceMatcher(None, node.id, similar[0]).ratio() >= 0.85 else "low"
                    self._add(CodeFinding(
                        "similar_name", f"「{node.id}」に似た定義名「{'、'.join(similar)}」があります。変数名のタイプミスの可能性があります。",
                        confidence, node.lineno, node.id, similar, self._evidence(node),
                    ))

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)  # 右辺を評価する前に左辺が定義されるとは扱わない。
        length = self._literal_length(node.value)
        # alias = items の後は別名経由で変更できるので長さを保持しない。
        if isinstance(node.value, ast.Name) and node.value.id in self.scope.lengths:
            self.scope.lengths.clear()
        for target in node.targets:
            self.visit(target)
            if isinstance(target, ast.Name) and length is not None and len(node.targets) == 1:
                self.scope.lengths[target.id] = length
            elif not isinstance(target, ast.Name):
                self.scope.lengths.clear()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            self.visit(node.value)
            self.visit(node.target)
            length = self._literal_length(node.value)
            if isinstance(node.target, ast.Name) and length is not None:
                self.scope.lengths[node.target.id] = length
        # 値のない注釈 x: int は、xの値を作らない。

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.visit_Name(ast.copy_location(ast.Name(node.target.id, ast.Load()), node.target))
        else:
            self.visit(node.target)
        self.visit(node.value)
        self.visit(node.target)
        self.scope.lengths.clear()

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        # 内包表記の := は内包表記の外側のスコープへ束縛する。
        old = self.scope
        while self.scope.is_comprehension:
            self.scope = self.scope.parent
        self.visit(node.target)
        self.scope = old

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self._bind(bound, node.lineno, "import")
            self.imports.append(ImportInfo(alias.name, None, bound, node.lineno))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            bound = alias.asname or alias.name
            if alias.name != "*":
                self._bind(bound, node.lineno, "import")
            self.imports.append(ImportInfo(module, alias.name, bound if alias.name != "*" else None, node.lineno))

    def _child(self, node: ast.AST, name: str, deferred: bool) -> _Scope:
        child = next(table for table in self.scope.table.get_children()
                     if table.get_name() == name and table.get_lineno() == node.lineno and table.get_id() not in self._children_used)
        self._children_used.add(child.get_id())
        params = {symbol.get_name() for symbol in child.get_symbols() if symbol.is_parameter()}
        return _Scope(child, self.scope, deferred or self.scope.deferred, bound=params)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        for value in [*getattr(node, "decorator_list", []), *node.args.defaults, *node.args.kw_defaults]:
            if value:
                self.visit(value)
        # アノテーションの評価時期はPython版やfuture設定によって異なるため警告対象外。
        if not isinstance(node, ast.Lambda):
            self._bind(node.name, node.lineno, "function")
        old = self.scope
        self.scope = self._child(node, "lambda" if isinstance(node, ast.Lambda) else node.name, True)
        for name in sorted(self.scope.bound):
            self.definitions.append(NameDefinition(name, node.lineno, self.scope.label, "parameter"))
        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            for statement in node.body:
                self.visit(statement)
        self.scope = old
        if getattr(node, "decorator_list", []):
            self.scope.lengths.clear()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function
    visit_Lambda = _function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for value in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(value)
        old = self.scope
        self.scope = self._child(node, node.name, False)
        for statement in node.body:
            self.visit(statement)
        self.scope = old
        self.scope.lengths.clear()
        self._bind(node.name, node.lineno, "class")

    def _comprehension(self, node) -> None:
        # 最初のiterableは外側で評価し、ループ変数は内包表記内だけに定義する。
        self.visit(node.generators[0].iter)
        old = self.scope
        kind = {ast.ListComp: "listcomp", ast.SetComp: "setcomp", ast.DictComp: "dictcomp", ast.GeneratorExp: "genexpr"}[type(node)]
        has_child = any(table.get_name() == kind and table.get_lineno() == node.lineno
                        for table in self.scope.table.get_children())
        if has_child:
            self.scope = self._child(node, kind, isinstance(node, ast.GeneratorExp))
        else:
            local_names = {item.id for generator in node.generators for item in ast.walk(generator.target)
                           if isinstance(item, ast.Name)}
            self.scope = _Scope(old.table, old, old.deferred, synthetic_names=local_names,
                                synthetic_label=f"{kind}@{node.lineno}")
        self.scope.is_comprehension = True
        for i, generator in enumerate(node.generators):
            if i:
                self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scope = old
        self.scope.lengths.clear()

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.visit(node.value)
        if isinstance(node.ctx, ast.Load):
            self.attributes.append(AttributeAccess(self._evidence(node), node.attr, node.lineno))

    @staticmethod
    def _literal_length(node) -> int | None:
        if isinstance(node, (ast.List, ast.Tuple)) and not any(isinstance(item, ast.Starred) for item in node.elts):
            return len(node.elts)
        return None

    @staticmethod
    def _integer(node) -> int | None:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = _CodeVisitor._integer(node.operand)
            return (-value if isinstance(node.op, ast.USub) else value) if value is not None else None
        return None

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit(node.value)
        self.visit(node.slice)
        if not isinstance(node.ctx, ast.Load):
            self.scope.lengths.clear()
            return
        length = self.scope.lengths.get(node.value.id) if isinstance(node.value, ast.Name) else self._literal_length(node.value)
        index = self._integer(node.slice)
        if length is not None and index is not None and not -length <= index < length:
            expression = self._evidence(node)
            self._add(CodeFinding(
                "index_out_of_range", f"「{expression}」では要素数{length}に対して位置{index}を指定しています。このアクセスが実行されれば範囲外となる形です。",
                "high", node.lineno, expression, (str(length), str(index)), expression,
            ))

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        # 引数の評価中のアクセスは確認するが、呼び出し後の変更は推測しない。
        self.scope.lengths.clear()

    def _suite(self, statements) -> None:
        self.scope.lengths.clear()
        for statement in statements:
            self.visit(statement)
        self.scope.lengths.clear()

    def visit_If(self, node) -> None:
        self.scope.lengths.clear()
        self.visit(node.test)
        self._suite(node.body)
        self._suite(node.orelse)

    visit_While = visit_If

    def visit_Try(self, node) -> None:
        self._suite(node.body)
        for handler in node.handlers:
            self.scope.lengths.clear()
            self.visit(handler)
        self._suite(node.orelse)
        self._suite(node.finalbody)

    visit_TryStar = visit_Try

    def visit_Match(self, node) -> None:
        self.scope.lengths.clear()
        self.visit(node.subject)
        for case in node.cases:
            self.scope.lengths.clear()
            self.visit(case)
        self.scope.lengths.clear()

    def visit_For(self, node) -> None:
        self.scope.lengths.clear()
        self.visit(node.iter)
        self.visit(node.target)
        self._suite(node.body)
        self._suite(node.orelse)

    visit_AsyncFor = visit_For

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type:
            self.visit(node.type)
        if node.name:
            self._bind(node.name, node.lineno, "exception")
        for statement in node.body:
            self.visit(statement)
        if node.name:
            self.scope.bound.discard(node.name)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.pattern:
            self.visit(node.pattern)
        if node.name:
            self._bind(node.name, node.lineno, "pattern")

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self._bind(node.name, node.lineno, "pattern")

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        self.generic_visit(node)
        if node.rest:
            self._bind(node.rest, node.lineno, "pattern")

    def visit_Global(self, node: ast.Global) -> None:
        pass

    visit_Nonlocal = visit_Global


def analyze_code(code: str, error: ParsedError | None = None) -> CodeAnalysis:
    """未定義候補・参照順序・import・属性・明白な範囲外アクセスを返す。"""
    if len(code) > 100_000:
        return CodeAnalysis("unavailable", notes=("コードが10万文字を超えるため、AST解析を省略しました。",))
    try:
        tree = ast.parse(code)
        if sum(1 for _ in ast.walk(tree)) > 20_000:
            return CodeAnalysis("unavailable", notes=("コードが複雑なためAST解析を省略しました。ログ解析は引き続き利用できます。",))
        if any(getattr(node, "type_params", ()) or type(node).__name__ == "TypeAlias" for node in ast.walk(tree)):
            return CodeAnalysis("unavailable", notes=("type文・型パラメータを含む構文のAST補助解析にはまだ対応していません。ログ解析は引き続き利用できます。",))
        table = symtable.symtable(code, "<pasted-code>", "exec")
        visitor = _CodeVisitor(code, tree, table)
        visitor.visit(tree)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        line = getattr(exc, "lineno", None)
        message = getattr(exc, "msg", str(exc))
        location = f"{line}行目付近で" if line else ""
        return CodeAnalysis("unavailable", notes=(f"{location}ASTを生成・解析できませんでした（{message}）。ログ解析の結果とヒントは引き続き表示します。",))
    except (KeyError, StopIteration):
        # 対応外の新しい構文などでASTとsymbol tableを対応付けられない場合。
        return CodeAnalysis("unavailable", notes=("この構文のスコープを安全に対応付けられないため、AST補助解析を省略しました。",))
    if error:
        name = (error.error_type or "").rsplit(".", 1)[-1]
        import_module = re.search(r"\bfrom ['\"]([^'\"]+)['\"]", error.message) if name == "ImportError" else None
        for item in visitor.imports:
            if error.line and item.line != error.line:
                continue
            target = error.target
            requested = item.module.lstrip(".") + (f".{item.imported_name}" if item.imported_name and item.imported_name != "*" else "")
            module_match = target and (requested == target or requested.startswith(target + "."))
            import_match = target and item.imported_name == target and (not import_module or item.module == import_module[1])
            if (name == "ModuleNotFoundError" and module_match) or (name == "ImportError" and import_match):
                expression = f"from {item.module} import {item.imported_name}" if item.imported_name else f"import {item.module}"
                visitor._add(CodeFinding("import_match", f"{item.line}行目の「{expression}」が、ログの「{target}」の読み込みに対応しています。モジュールの存在や実行環境は静的解析では確認できません。", "high", item.line, target, (item.module,), expression))
        if name == "AttributeError":
            for item in visitor.attributes:
                if (not error.line or item.line == error.line) and item.attribute == error.target:
                    visitor._add(CodeFinding("attribute_access", f"{item.line}行目の「{item.expression}」で属性「{item.attribute}」へアクセスしています。その属性が実際の値にあるかは、型や実行時の値を確認してください。", "high", item.line, item.attribute, (item.expression,), item.expression))
    facts = ()
    if not visitor.dynamic_names:
        try:
            literal = analyze_literals(code, tree)
            # 既存visitorの候補も、明示的な到達不能・捕捉済みの場所では表示しない。
            dead, alive = set(), set()
            for node in ast.walk(tree):
                key = None
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    key = (node.lineno, node.id)
                elif isinstance(node, ast.Subscript):
                    key = (node.lineno, (ast.get_source_segment(code, node) or '')[:240])
                if key:
                    (dead if id(node) in literal.unreachable else alive).add(key)
            visitor.findings = [f for f in visitor.findings if (f.line, f.target) not in dead - alive
                                and f.kind != 'index_out_of_range']
            visitor._seen = {(f.kind, f.line, f.target) for f in visitor.findings}
            for finding in literal.findings:
                visitor._add(finding)
            visitor.notes.extend(literal.notes)
            facts = tuple(literal.facts)
        except (RecursionError, MemoryError):
            visitor.notes.append('型・値の補助解析の上限に達しました。従来の名前・ログ解析は利用できます。')
    return CodeAnalysis("parsed", tuple(visitor.findings), tuple(visitor.definitions), tuple(visitor.uses),
                        tuple(visitor.imports), tuple(visitor.attributes), tuple(visitor.notes), facts)
