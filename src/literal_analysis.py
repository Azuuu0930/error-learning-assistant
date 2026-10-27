"""実行・eval・ユーザーimportをしない、保守的な型/値/経路の補助解析。

正確な組み込みリテラルと直接の関数定義だけを扱う。未知の呼び出し、
別名、書き込みを越えて値・長さ・辞書キーを持ち越さない。
"""
import ast
import builtins
from dataclasses import dataclass, field
import inspect
import operator

from src.models import CodeFact, CodeFinding
from src.safe_summaries import SCALARS, direct_iteration_mutation, pure_function, simple_class


UNKNOWN = object()
TYPES = {t.__name__: t for t in (int, float, str, bytes, list, tuple, dict, set, bool, type(None))}
NUMBERS = {'int', 'float', 'bool'}
MUTABLE = {'list', 'dict', 'set'}
SEQUENCES = {'list', 'tuple', 'str', 'bytes'}


@dataclass(frozen=True)
class Value:
    kind: str = 'unknown'
    constant: object = UNKNOWN
    length: int | None = None
    keys: frozenset | None = None
    origin: str = ''
    class_name: str = ''
    defined_attributes: tuple[str, ...] = ()
    safe_contents: bool = False


@dataclass
class State:
    values: dict[str, Value] = field(default_factory=dict)
    functions: dict[str, ast.AST] = field(default_factory=dict)
    explicit: set[str] = field(default_factory=set)
    definite: set[str] = field(default_factory=set)
    possible: dict[str, str] = field(default_factory=dict)
    raised: str | None = None
    may_raise: bool = False
    alive: bool = True
    control: str = ''
    builtins_trusted: bool = True
    classes: dict = field(default_factory=dict)

    def copy(self):
        return State(dict(self.values), dict(self.functions), set(self.explicit), set(self.definite),
                     dict(self.possible), self.raised, self.may_raise, self.alive, self.control, self.builtins_trusted,
                     dict(self.classes))


def signature(node):
    """引数の名前・種類・省略可否だけをinspectで照合する。default値は実行しない。"""
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    required = len(positional) - len(arguments.defaults)
    params = []
    for i, arg in enumerate(positional):
        kind = inspect.Parameter.POSITIONAL_ONLY if i < len(arguments.posonlyargs) else inspect.Parameter.POSITIONAL_OR_KEYWORD
        params.append(inspect.Parameter(arg.arg, kind, default=inspect.Parameter.empty if i < required else UNKNOWN))
    if arguments.vararg:
        params.append(inspect.Parameter(arguments.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        params.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                                        default=inspect.Parameter.empty if default is None else UNKNOWN))
    if arguments.kwarg:
        params.append(inspect.Parameter(arguments.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


class LiteralAnalysis:
    def __init__(self, code: str):
        self.code = code
        self.state = State()
        self.findings: list[CodeFinding] = []
        self.facts: list[CodeFact] = []
        self.notes: list[str] = []
        self.unreachable: set[int] = set()
        self.suppressed: set[tuple[int, str]] = set()
        self.handlers: list[set[str]] = []
        self.analyzed_functions: set[int] = set()
        self.quiet = False
        self.epoch = 0
        self._seen = set()
        self.builtin_uses: set[str] = set()
        self.return_value = Value()

    def text(self, node):
        return (ast.get_source_segment(self.code, node) or '')[:240]

    def invalidate(self, may_run_user=False):
        self.state.values.clear()
        self.state.functions.clear()
        self.state.classes.clear()
        self.epoch += 1
        if may_run_user:
            self.state.builtins_trusted = False

    def note(self, text):
        if text not in self.notes and len(self.notes) < 50:
            self.notes.append(text)

    @staticmethod
    def catches(handlers, exception):
        if '*' in handlers:
            return True
        exc_type = getattr(builtins, exception, None)
        return any(isinstance((kind := getattr(builtins, name, None)), type)
                   and issubclass(kind, BaseException) and exc_type and issubclass(exc_type, kind) for name in handlers)

    def fact(self, kind, node, subject, details=None):
        fact = CodeFact(kind, node.lineno, subject, details or {})
        if not self.quiet and fact not in self.facts and len(self.facts) < 100:
            self.facts.append(fact)

    def emit(self, node, kind, message, exception=None, target=None, related=(), confidence='high', details=None):
        details = dict(details or {})
        if exception:
            details['exception_type'] = exception
            self.state.raised = exception
            groups = [self.handler_names(handler) for handlers in self.handlers for handler in handlers]
            if any(self.catches(group, exception) for group in groups):
                self.suppressed.add((node.lineno, exception))
                self.note(f'{node.lineno}行目の{exception}は、exceptで捕捉・処理される経路です。プログラム全体の正常動作を保証する情報ではありません。')
                self.fact('handled_exception', node, exception)
                return
            if any('?' in group for group in groups):
                self.note(f'{node.lineno}行目の{exception}はexceptで処理できる可能性がありますが、捕捉する型が静的に確定できません。')
                return
        key = (kind, node.lineno, target or self.text(node))
        if self.quiet or key in self._seen:
            return
        self._seen.add(key)
        if len(self.findings) < 50:
            self.findings.append(CodeFinding(kind, message, confidence, node.lineno,
                                             target or self.text(node), tuple(related), self.text(node), details))

    def dead(self, nodes):
        for node in nodes:
            self.unreachable.update(id(item) for item in ast.walk(node))

    def builtin(self, name):
        return self.state.builtins_trusted and name not in self.state.explicit

    def bind(self, target, value=Value()):
        if isinstance(target, ast.Name):
            self.state.explicit.add(target.id)
            self.state.definite.add(target.id)
            self.state.possible.pop(target.id, None)
            self.state.functions.pop(target.id, None)
            self.state.classes.pop(target.id, None)
            self.state.values.pop(target.id, None)
            if value.kind != 'unknown':
                self.state.values[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self.bind(item)
        elif isinstance(target, ast.Starred):
            self.bind(target.value)
        else:
            self.expr(target)
            self.invalidate()

    def suite(self, statements):
        for position, statement in enumerate(statements):
            if not self.state.alive or self.state.raised:
                self.dead(statements[position:])
                break
            self.stmt(statement)

    def joined(self, states, reason='分岐'):
        active = [s for s in states if s.alive and not s.raised]
        if not active:
            result = states[0].copy()
            return result
        result = active[0].copy()
        result.definite = set.intersection(*(s.definite for s in active))
        result.explicit = set.union(*(s.explicit for s in states))
        possible = set.union(*(s.definite | set(s.possible) for s in states))
        result.possible = {name: next((s.possible[name] for s in states if name in s.possible), reason)
                           for name in possible - result.definite}
        result.values = {}
        result.functions = {}
        result.classes = {}
        for name in result.definite:
            values = [s.values.get(name, Value()) for s in active]
            if values[0].kind != 'unknown' and all(v.kind == values[0].kind for v in values):
                if all(v == values[0] for v in values):
                    result.values[name] = values[0]
                elif values[0].kind != 'instance':
                    # A shared Python type is useful for literal containers;
                    # different class models cannot share attribute guarantees.
                    result.values[name] = Value(values[0].kind)
            functions = [s.functions.get(name) for s in active]
            if functions[0] is not None and all(f is functions[0] for f in functions):
                result.functions[name] = functions[0]
            classes = [s.classes.get(name) for s in active]
            if classes[0] is not None and all(c is classes[0] for c in classes):
                result.classes[name] = classes[0]
        result.raised = None
        result.may_raise = any(s.may_raise for s in states)
        result.builtins_trusted = all(s.builtins_trusted for s in states)
        result.alive = True
        result.control = ''
        return result

    def branch(self, statements, state, *, quiet=None):
        prior_state, prior_quiet = self.state, self.quiet
        self.state = state.copy()
        if quiet is not None:
            self.quiet = quiet
        self.suite(statements)
        result = self.state
        self.state, self.quiet = prior_state, prior_quiet
        return result

    def stmt(self, node):
        if isinstance(node, ast.Assign):
            value = self.expr(node.value)
            if self.state.raised:
                return
            # 共有された可変オブジェクトのキーや長さは保持しない。
            if (isinstance(node.value, ast.Name) or len(node.targets) != 1) and value.kind in MUTABLE:
                self.invalidate()
                value = Value(value.kind)
            for target in node.targets:
                self.bind(target, value)
        elif isinstance(node, ast.AnnAssign):
            if node.value:
                value = self.expr(node.value)
                if not self.state.raised:
                    self.bind(node.target, value)
            if not isinstance(node.annotation, (ast.Name, ast.Constant)):
                self.invalidate(may_run_user=True)
        elif isinstance(node, ast.AugAssign):
            self.expr(node.target)
            self.expr(node.value)
            self.bind(node.target)
            self.invalidate()
        elif isinstance(node, ast.Expr):
            self.expr(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for value in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
                if value:
                    self.expr(value)
            # アノテーションの評価時期はPython版/futureで異なるため、
            # その副作用を越えて以前の値を断定しない。
            if node.returns or any(arg.annotation for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                                   + ([node.args.vararg] if node.args.vararg else []) + ([node.args.kwarg] if node.args.kwarg else [])):
                self.invalidate(may_run_user=True)
            self.bind(ast.Name(id=node.name))
            if not node.decorator_list:
                self.state.functions[node.name] = node
            else:
                self.invalidate(may_run_user=True)
        elif isinstance(node, ast.ClassDef):
            model = simple_class(node) if self.state.builtins_trusted else None
            if model is None:
                # クラス本体・メタクラス・decoratorの効果は推測しない。
                self.invalidate(may_run_user=True)
                self.bind(ast.Name(id=node.name))
            else:
                self.bind(ast.Name(id=node.name))
                self.state.classes[node.name] = model
                for attribute, line in model.attributes:
                    self.fact('defined_attribute', ast.Constant(lineno=line), attribute, {'class_name': node.name})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self.invalidate()
            for alias in node.names:
                self.bind(ast.Name(id=alias.asname or (alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name)))
        elif isinstance(node, ast.If):
            condition = self.expr(node.test)
            if condition.kind == 'unknown':
                self.invalidate(may_run_user=True)
            prior = self.state.copy()
            if condition.constant is not UNKNOWN:
                chosen, skipped = (node.body, node.orelse) if bool(condition.constant) else (node.orelse, node.body)
                self.dead(skipped)
                taken = self.branch(chosen, prior)
                # 構文上は存在するが実行されない代入も、未束縛の説明には使える。
                for item in skipped:
                    for name in ast.walk(item):
                        if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store) and name.id not in taken.definite:
                            taken.possible[name.id] = '分岐'
                self.state = taken
            else:
                # 実行されるか不明な枝内の問題は警告にせず、定義の合流だけ行う。
                self.state = self.joined([self.branch(node.body, prior, quiet=True),
                                          self.branch(node.orelse, prior, quiet=True)])
        elif isinstance(node, (ast.For, ast.While)):
            iterable = self.expr(node.iter if isinstance(node, ast.For) else node.test)
            mutation = direct_iteration_mutation(node, iterable) if isinstance(node, ast.For) else None
            if mutation is not None:
                self.emit(node, 'iteration_mutation',
                          f'{iterable.kind} の反復中に要素数を変更しています。次の反復へ進むとRuntimeErrorになる形です。',
                          'RuntimeError', target=node.iter.id,
                          details={'container_type': iterable.kind, 'mutation_line': mutation.lineno})
                return
            prior = self.state.copy()
            if isinstance(node, ast.While) and iterable.kind == 'unknown':
                self.invalidate(may_run_user=True)
            self.invalidate()
            body_start = self.state.copy()
            empty = iterable.length == 0 if isinstance(node, ast.For) else iterable.constant is not UNKNOWN and not iterable.constant
            if empty:
                self.dead(node.body)
                for statement in node.body:
                    for item in ast.walk(statement):
                        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id not in self.state.definite:
                            self.state.possible[item.id] = '空ループ'
                if isinstance(node, ast.For):
                    for item in ast.walk(node.target):
                        if isinstance(item, ast.Name) and item.id not in self.state.definite:
                            self.state.possible[item.id] = '空ループ'
            else:
                if isinstance(node, ast.For):
                    self.bind(node.target)
                    body_start = self.state.copy()
                guaranteed = (iterable.length is not None and iterable.length > 0
                              if isinstance(node, ast.For) else iterable.constant is not UNKNOWN and bool(iterable.constant))
                body = self.branch(node.body, body_start, quiet=self.quiet or not guaranteed)
                if body.control in {'break', 'continue'}:
                    body.alive = True
                nonempty = isinstance(node, ast.For) and iterable.length is not None and iterable.length > 0
                has_exit = any(isinstance(item, (ast.Break, ast.Continue, ast.Return, ast.Raise)) for statement in node.body for item in ast.walk(statement))
                self.state = body if nonempty and not has_exit else self.joined([prior, body], 'ループ')
            if not empty and body.control == 'break' and nonempty:
                self.dead(node.orelse)
                self.state.control, self.state.alive = '', True
            elif not empty and has_exit:
                # break等があるループのelseは実行されない場合がある。
                self.invalidate()
                self.state = self.joined([self.state, self.branch(node.orelse, self.state, quiet=True)], 'ループ')
            else:
                self.suite(node.orelse)
            self.invalidate()
            if (isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and bool(node.test.value)
                    and not any(isinstance(i, (ast.Break, ast.Return, ast.Raise)) for s in node.body for i in ast.walk(s))):
                self.state.alive, self.state.control = False, 'nonterminating'
        elif isinstance(node, ast.Try):
            self.try_statement(node)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                self.expr(item.context_expr)
                if item.optional_vars:
                    self.bind(item.optional_vars)
            self.invalidate(may_run_user=True)  # __enter__/__aenter__は任意の処理を呼べる。
            prior_quiet = self.quiet
            self.quiet = True  # 未知の__exit__が例外を抑制する可能性がある。
            self.suite(node.body)
            self.quiet = prior_quiet
            self.state.raised = None
            self.invalidate()
        elif isinstance(node, ast.Return):
            self.return_value = self.expr(node.value) if node.value else Value('NoneType', None)
            self.state.alive, self.state.control = False, 'return'
        elif isinstance(node, (ast.Break, ast.Continue)):
            self.state.alive, self.state.control = False, type(node).__name__.lower()
        elif isinstance(node, ast.Raise):
            if node.exc:
                self.expr(node.exc)
            self.state.alive = False
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.state.definite.discard(target.id)
                    self.state.possible[target.id] = '削除'
            self.invalidate()
        elif isinstance(node, ast.Assert):
            condition = self.expr(node.test)
            if condition.kind == 'unknown':
                self.invalidate(may_run_user=True)
            if condition.constant is not UNKNOWN and not condition.constant:
                if node.msg:
                    self.expr(node.msg)
                if not self.state.raised:
                    self.emit(node, 'assertion_failure',
                              'assert の条件が偽と分かる形です。このassertが有効な実行ではAssertionErrorになります。',
                              'AssertionError')
            elif node.msg:
                if condition.constant is not UNKNOWN:
                    self.dead([node.msg])
                else:
                    self.invalidate(may_run_user=True)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.invalidate()
        elif not isinstance(node, ast.Pass):
            # match、例外グループなど未対応の経路では推論しない。
            self.invalidate(may_run_user=True)

    def handler_names(self, handler):
        if handler.type is None:
            return {'*'}
        expressions = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        result = set()
        for item in expressions:
            if isinstance(item, ast.Name):
                known = self.state.values.get(item.id, Value())
                if known.kind == 'exception_type':
                    result.add(known.origin)
                elif self.builtin(item.id) and item.id in vars(builtins):
                    result.add(item.id)
                else:
                    result.add('?')
            else:
                result.add('?')
        return result

    def try_statement(self, node):
        prior = self.state.copy()
        prior_quiet = self.quiet
        if any(isinstance(item, (ast.Return, ast.Raise, ast.Break, ast.Continue)) for statement in node.finalbody for item in ast.walk(statement)):
            # finallyの制御移動で途中の例外が外へ出ない可能性がある。
            self.quiet = True
        self.handlers.append(node.handlers)
        body = self.branch(node.body, prior)
        self.handlers.pop()
        if body.raised:
            self.state = body
            groups = [self.handler_names(h) for h in node.handlers]
            match = next((i for i, group in enumerate(groups) if self.catches(group, body.raised)), None)
            if match is None:
                self.state = body
            else:
                handler = node.handlers[match]
                self.state = body.copy()
                self.state.raised, self.state.alive, self.state.control = None, True, ''
                if handler.name:
                    self.bind(ast.Name(id=handler.name))
                self.suite(handler.body)
                if handler.name:
                    self.state.definite.discard(handler.name)
                    self.state.values.pop(handler.name, None)
        else:
            normal = self.branch(node.orelse, body)
            paths = [normal]
            for handler in node.handlers:
                handler_state = prior.copy()
                if handler.name:
                    handler_state.definite.add(handler.name)
                    handler_state.explicit.add(handler.name)
                # 未知の呼び出しが本当に例外を送出するか分からない。
                path = self.branch(handler.body, handler_state, quiet=True)
                if handler.name:
                    path.definite.discard(handler.name)
                    path.values.pop(handler.name, None)
                paths.append(path)
            self.state = self.joined(paths, '例外処理')
        raised, alive, control = self.state.raised, self.state.alive, self.state.control
        self.quiet = prior_quiet
        self.state.raised, self.state.alive, self.state.control = None, True, ''
        self.suite(node.finalbody)
        if not self.state.raised and not self.state.control:
            self.state.raised, self.state.alive, self.state.control = raised, alive, control

    def expr(self, node):
        if self.state.raised:
            return Value()
        if isinstance(node, ast.Constant):
            kind = type(node.value).__name__
            if kind in TYPES:
                value = node.value
                safe = not isinstance(value, (str, bytes)) or len(value) <= 4096
                if type(value) is int and value.bit_length() > 256:
                    safe = False
                return Value(kind, value if safe else UNKNOWN, len(value) if isinstance(value, (str, bytes)) else None)
        elif isinstance(node, ast.Name):
            reason = self.state.possible.get(node.id)
            if reason and node.id not in self.state.definite:
                if reason in {'ループ', '空ループ'}:
                    message = f'ループが一度も実行されない経路では「{node.id}」が未定義になる可能性があります。全ての経路で定義されるとは限りません。'
                else:
                    message = f'「{node.id}」は{reason}の一部の経路でしか定義されない可能性があります。全ての経路で定義されるとは限りません。'
                self.emit(node, 'possibly_unbound', message, target=node.id, confidence='medium')
            if self.builtin(node.id) and node.id in vars(builtins):
                self.builtin_uses.add(node.id)
                self.fact('builtin_reference', node, node.id)
                builtin_type = vars(builtins)[node.id]
                if isinstance(builtin_type, type) and issubclass(builtin_type, BaseException):
                    return Value('exception_type', origin=node.id)
            return self.state.values.get(node.id, Value())
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            elements = [self.expr(item) for item in node.elts]
            if isinstance(node, ast.Set) and any(v.kind not in NUMBERS | {'str', 'bytes', 'NoneType'} for v in elements):
                self.invalidate(may_run_user=True)
            kind = {ast.List: 'list', ast.Tuple: 'tuple', ast.Set: 'set'}[type(node)]
            if kind == 'set' and all(v.constant is not UNKNOWN and v.kind in SCALARS for v in elements):
                keys = frozenset(v.constant for v in elements)
                return Value(kind, length=len(keys), keys=keys)
            return Value(kind, length=len(node.elts) if not any(isinstance(i, ast.Starred) for i in node.elts) else None)
        elif isinstance(node, ast.Dict):
            keys = []
            safe_contents = True
            complete = True
            for key, value in zip(node.keys, node.values):
                known = self.expr(key) if key else Value()
                member = self.expr(value)
                safe_contents = safe_contents and member.kind in SCALARS
                if known.constant is UNKNOWN or known.kind not in NUMBERS | {'str', 'bytes', 'NoneType'}:
                    complete = False
                else:
                    keys.append(known.constant)
            if not complete:
                self.invalidate(may_run_user=True)
            key_set = frozenset(keys) if complete else None
            return Value('dict', length=len(key_set) if key_set is not None else None, keys=key_set,
                         safe_contents=safe_contents)
        elif isinstance(node, ast.UnaryOp):
            value = self.expr(node.operand)
            if isinstance(node.op, ast.Not):
                if value.kind == 'unknown':
                    self.invalidate(may_run_user=True)
                return Value('bool', not value.constant if value.constant is not UNKNOWN else UNKNOWN)
            if value.kind in NUMBERS:
                functions = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}
                if type(node.op) in functions and value.constant is not UNKNOWN and (not isinstance(node.op, ast.Invert) or value.kind != 'float'):
                    result = functions[type(node.op)](value.constant)
                    return Value(type(result).__name__, result)
                return Value(value.kind)
            if value.kind == 'unknown':
                self.invalidate(may_run_user=True)
        elif isinstance(node, ast.BinOp):
            left, right = self.expr(node.left), self.expr(node.right)
            if self.state.raised:
                return Value()
            numeric = left.kind in NUMBERS and right.kind in NUMBERS
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and numeric and right.constant is not UNKNOWN and right.constant == 0:
                self.emit(node, 'zero_division', f'「{self.text(node)}」は数値を0で除算する形です。この行が実行されるとZeroDivisionErrorになります。', 'ZeroDivisionError')
            elif isinstance(node.op, ast.Add):
                allowed = numeric or left.kind == right.kind and left.kind in {'str', 'bytes', 'list', 'tuple'}
                if left.kind != 'unknown' and right.kind != 'unknown' and not allowed:
                    extra = ' input の戻り値は文字列strです。数値として使う場合は数値変換が必要な可能性があります。' if 'input' in {left.origin, right.origin} else ''
                    self.emit(node, 'incompatible_operation', f'「{self.text(node)}」は {left.kind} と {right.kind} の不正な加算です。この型の組み合わせでは加算できないため、実行されるとTypeErrorになります。{extra}', 'TypeError', details={'operator': '+', 'left_type': left.kind, 'right_type': right.kind})
                elif allowed:
                    return Value('float' if numeric and 'float' in {left.kind, right.kind} else ('int' if numeric else left.kind))
            if numeric:
                return Value('float' if isinstance(node.op, ast.Div) or 'float' in {left.kind, right.kind} else 'int')
            self.invalidate(may_run_user=True)
        elif isinstance(node, ast.Compare):
            left = self.expr(node.left)
            for position, (op, right_node) in enumerate(zip(node.ops, node.comparators)):
                right = self.expr(right_node)
                if isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) and left.kind != 'unknown' and right.kind != 'unknown':
                    allowed = left.kind in NUMBERS and right.kind in NUMBERS or left.kind == right.kind and left.kind in {'str', 'bytes', 'list', 'tuple', 'set'}
                    if not allowed:
                        operator_name = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}[type(op)]
                        self.emit(node, 'incompatible_operation', f'「{self.text(node)}」では {left.kind} と {right.kind} の大小比較はできない組み合わせです。実行されるとTypeErrorになります。', 'TypeError', details={'operator': operator_name, 'left_type': left.kind, 'right_type': right.kind})
                        return Value()
                comparisons = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                               ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
                if left.constant is not UNKNOWN and right.constant is not UNKNOWN and type(op) in comparisons:
                    try:
                        matched = comparisons[type(op)](left.constant, right.constant)
                    except TypeError:
                        return Value('bool')
                    if not matched:
                        self.dead(node.comparators[position + 1:])
                        return Value('bool', False)
                else:
                    if left.kind in MUTABLE | {'tuple', 'unknown'} or right.kind in MUTABLE | {'tuple', 'unknown'}:
                        self.invalidate(may_run_user=True)
                    if position + 1 < len(node.ops):
                        self.invalidate(may_run_user=True)
                        return Value('bool')
                    return Value('bool')
                left = right
            return Value('bool', True)
        elif isinstance(node, ast.Attribute):
            value = self.expr(node.value)
            if value.kind == 'instance':
                if not isinstance(node.ctx, ast.Load):
                    self.invalidate()
                    return Value()
                known = set(value.defined_attributes) | set(dir(object)) | {'__dict__', '__weakref__', '__module__', '__doc__'}
                if node.attr not in known:
                    self.emit(node, 'missing_attribute',
                              f'{value.class_name} の単純な初期化で定義された属性に {node.attr} がありません。このアクセスが実行されるとAttributeErrorになります。',
                              'AttributeError', target=node.attr,
                              details={'receiver_type': value.class_name, 'class_name': value.class_name,
                                       'attribute': node.attr, 'defined_attributes': list(value.defined_attributes)})
                return Value()
            cls = TYPES.get(value.kind)
            if cls is None:
                self.invalidate(may_run_user=True)
            if cls is not None and not hasattr(cls, node.attr):
                prefix = f'「{self.text(node.value)}」は None（NoneType）です。' if value.kind == 'NoneType' else ''
                self.emit(node, 'missing_attribute', f'{prefix}{value.kind} の属性 {node.attr} はありません。「{self.text(node)}」が実行されるとAttributeErrorになります。意図した操作や値を確認してください。', 'AttributeError', target=node.attr, details={'receiver_type': value.kind, 'attribute': node.attr})
        elif isinstance(node, ast.Subscript):
            value = self.expr(node.value)
            epoch = self.epoch
            index = self.expr(node.slice)
            if epoch != self.epoch and value.kind in MUTABLE:
                value = Value(value.kind)
            if value.kind in SEQUENCES and not isinstance(node.slice, ast.Slice):
                if index.kind not in {'int', 'bool', 'unknown'}:
                    self.emit(node, 'invalid_index_type', f'{value.kind} の添字が {index.kind} です。整数またはslice以外では要素を取り出せず、この行が実行されるとTypeErrorになります。', 'TypeError', details={'receiver_type': value.kind, 'index_type': index.kind})
                elif value.length is not None and index.constant is not UNKNOWN and type(index.constant) in {int, bool} and not -value.length <= index.constant < value.length:
                    self.emit(node, 'index_out_of_range', f'「{self.text(node)}」では要素数{value.length}に対して位置{index.constant}を指定しています。このアクセスが実行されれば範囲外となる形です。', 'IndexError', related=(str(value.length), str(index.constant)))
            if value.kind == 'dict':
                if index.kind in MUTABLE:
                    self.emit(node, 'unhashable_key', f'{index.kind} は辞書キーとして使えないハッシュ化できない型です。この行が実行されるとTypeErrorになります。', 'TypeError')
                elif isinstance(node.ctx, ast.Load) and value.keys is not None and index.constant is not UNKNOWN and index.constant not in value.keys:
                    self.emit(node, 'missing_key', f'辞書「{self.text(node.value)}」にキー {index.constant!r} は存在しないため、このアクセスが実行されるとKeyErrorになります。', 'KeyError')
                if index.kind == 'tuple':
                    self.invalidate(may_run_user=True)
            if value.kind not in SEQUENCES | {'dict'} or index.kind == 'unknown' and not isinstance(node.slice, ast.Slice):
                self.invalidate(may_run_user=True)
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.invalidate()
        elif isinstance(node, ast.Call):
            return self.call(node)
        elif isinstance(node, ast.NamedExpr):
            value = self.expr(node.value)
            self.bind(node.target, value)
            return value
        elif isinstance(node, ast.BoolOp):
            result = Value()
            for i, value_node in enumerate(node.values):
                result = self.expr(value_node)
                if result.constant is UNKNOWN:
                    # 条件付きの右辺を確実に実行されるものとして診断しない。
                    self.invalidate(may_run_user=True)
                    return Value()
                if bool(result.constant) == isinstance(node.op, ast.Or):
                    self.dead(node.values[i + 1:])
                    return result
            return result
        elif isinstance(node, ast.Slice):
            for value in [node.lower, node.upper, node.step]:
                if value:
                    bound = self.expr(value)
                    if bound.kind not in {'int', 'bool', 'NoneType'}:
                        self.invalidate(may_run_user=True)
        elif isinstance(node, ast.IfExp):
            condition = self.expr(node.test)
            if condition.constant is not UNKNOWN:
                chosen, skipped = (node.body, node.orelse) if condition.constant else (node.orelse, node.body)
                self.dead([skipped])
                return self.expr(chosen)
            self.invalidate(may_run_user=True)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom)):
            self.invalidate(may_run_user=True)
        else:
            # 未対応の式にもf-string、lambdaのdefault等の実行効果がある。
            self.invalidate(may_run_user=True)
        return Value()

    def call(self, node):
        function = self.state.functions.get(node.func.id) if isinstance(node.func, ast.Name) else None
        model = self.state.classes.get(node.func.id) if isinstance(node.func, ast.Name) else None
        epoch = self.epoch
        self.expr(node.func)
        args = [self.expr(arg) for arg in node.args]
        keyword_values = {keyword.arg: self.expr(keyword.value) for keyword in node.keywords}
        if self.state.raised:
            return Value()
        if self.epoch != epoch:
            function = None  # 引数の評価が__defaults__/__code__等を変える場合もある。
            model = None
        expanded = any(isinstance(arg, ast.Starred) for arg in node.args) or any(k.arg is None for k in node.keywords)
        if model is not None and not expanded:
            # __init__ can only store exact literals or arguments on this fresh
            # instance. Invalid/expanded binding is deliberately left unknown.
            try:
                if model.initializer:
                    signature(model.initializer).bind(UNKNOWN, *args, **keyword_values)
                elif args or keyword_values:
                    raise TypeError('object() takes no arguments')
            except TypeError:
                self.invalidate(may_run_user=True)
                return Value()
            return Value('instance', class_name=model.name,
                         defined_attributes=tuple(sorted({name for name, _ in model.attributes})))
        if function is not None and not expanded:
            sig = signature(function)
            positional = [p for p in sig.parameters.values() if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD}]
            kwargs = {k.arg: UNKNOWN for k in node.keywords}
            accepts_kwargs = function.args.kwarg is not None
            normal_keywords = {a.arg for a in [*function.args.args, *function.args.kwonlyargs]}
            unexpected = next((k for k in kwargs if k not in normal_keywords), None)
            message = None
            minimum = sum(p.default is p.empty and p.kind not in {p.VAR_POSITIONAL, p.VAR_KEYWORD} for p in sig.parameters.values())
            details = {'function_name': function.name, 'required_count': minimum,
                       'supplied_count': len(args) + len(kwargs), 'maximum_positional': len(positional)}
            if unexpected and not accepts_kwargs:
                message = f'関数 {function.name} に引数 {unexpected} は定義されていないため、このkeyword argumentは渡せません。'
                details.update(argument_issue='unexpected_keyword', keyword=unexpected)
            elif len(args) > len(positional) and function.args.vararg is None:
                message = f'関数 {function.name} の定義より多い位置引数です。最大 {len(positional)} 個に対して {len(args)} 個を渡しています。'
                details['argument_issue'] = 'too_many'
            else:
                try:
                    sig.bind(*([UNKNOWN] * len(args)), **kwargs)
                except TypeError as exc:
                    message = f'{function.name} は最低 {minimum} 個の引数が必要です。今回 {len(args) + len(kwargs)} 個の引数しか渡していない、または束縛が合わない可能性があります（{exc}）。'
                    duplicates = [p.name for p in positional[:len(args)] if p.kind == p.POSITIONAL_OR_KEYWORD and p.name in kwargs]
                    details['argument_issue'] = 'duplicate' if duplicates else 'missing'
            if message:
                self.emit(node, 'call_arguments', message, 'TypeError', target=function.name, details=details)
                return Value()
            if (args or keyword_values) and all(v.kind in SCALARS for v in [*args, *keyword_values.values()]) and pure_function(function):
                return self.pure_call(function, sig, args, keyword_values)
            if (id(function) not in self.analyzed_functions and not self.handlers
                    and not isinstance(function, ast.AsyncFunctionDef) and not self.is_generator(function)):
                self.analyzed_functions.add(id(function))
                outer = self.state
                params = set(sig.parameters)
                locals_ = self.local_names(function.body)
                self.state = State(explicit=outer.explicit | locals_ | params,
                                   definite=(outer.definite - locals_) | params,
                                   functions={name: f for name, f in outer.functions.items() if name not in locals_ | params},
                                   builtins_trusted=outer.builtins_trusted)
                self.suite(function.body)
                # 関数内のreturn/ローカル束縛を呼び出し元へ流出させない。
                self.state = outer
            self.invalidate(may_run_user=True)
            self.state.may_raise = True
            return Value()
        if isinstance(node.func, ast.Name) and self.builtin(node.func.id) and not expanded:
            name = node.func.id
            if name == 'iter' and len(args) == 1 and not node.keywords:
                if args[0].kind in SEQUENCES | {'dict', 'set', 'range', 'iterator'}:
                    return Value('iterator', length=0 if args[0].length == 0 else None)
            if name == 'next' and 1 <= len(args) <= 2 and not node.keywords and args[0].kind == 'iterator':
                if args[0].length == 0:
                    if len(args) == 2:
                        return args[1]
                    self.emit(node, 'empty_iterator',
                              '既知の空イテレータに既定値なしでnextを使っています。この呼び出しが実行されるとStopIterationになります。',
                              'StopIteration')
                    return Value()
                self.invalidate()
                return Value()
            if name == 'input':
                if any(a.kind not in TYPES or a.kind in MUTABLE | {'tuple'} for a in args):
                    self.invalidate(may_run_user=True)
                return Value('str', origin='input')
            if name in {'int', 'float', 'str', 'bytes', 'bool', 'list', 'tuple', 'dict', 'set'} and not node.keywords:
                if any(a.kind not in TYPES or a.kind in MUTABLE | {'tuple'} for a in args):
                    self.invalidate(may_run_user=True)
                    return Value()
                if name == 'int' and len(args) == 1 and args[0].kind == 'str' and args[0].constant is not UNKNOWN:
                    try:
                        int(args[0].constant)
                    except ValueError:
                        self.emit(node, 'invalid_conversion', f'「{args[0].constant}」は整数として読めない内容なのでintへの変換はできない形です。この行が実行されるとValueErrorになります。', 'ValueError')
                return Value(name)
            if name == 'range' and 1 <= len(args) <= 3 and all(a.kind in {'int', 'bool'} and a.constant is not UNKNOWN for a in args):
                try:
                    return Value('range', length=len(range(*(a.constant for a in args))))
                except (ValueError, OverflowError):
                    return Value('range')
            if name == 'len':
                if any(a.kind not in TYPES or a.kind in MUTABLE | {'tuple'} for a in args):
                    self.invalidate(may_run_user=True)
                return Value('int')
            if name == 'print' and not node.keywords and all(a.kind in TYPES and a.kind not in MUTABLE | {'tuple'} for a in args):
                return Value('NoneType', None)
        self.invalidate(may_run_user=True)
        self.state.may_raise = True
        return Value()

    def pure_call(self, function, sig, args, keywords):
        """Transfer values through a bounded, syntactically proven pure body."""
        bound = sig.bind(*args, **keywords)
        positional = [*function.args.posonlyargs, *function.args.args]
        defaults = dict(zip((a.arg for a in positional[-len(function.args.defaults):]), function.args.defaults)) if function.args.defaults else {}
        defaults.update({a.arg: d for a, d in zip(function.args.kwonlyargs, function.args.kw_defaults) if d is not None})
        outer, prior_return = self.state, self.return_value
        values = dict(bound.arguments)
        for name, default in defaults.items():
            if name not in values:
                values[name] = self.expr(default)
        names = self.local_names(function.body) | set(sig.parameters)
        self.state = State(values=values, explicit=outer.explicit | names, definite=set(values),
                           builtins_trusted=outer.builtins_trusted)
        start = self.epoch
        self.return_value = Value()
        self.suite(function.body)
        result, raised = self.return_value, self.state.raised
        self.state, self.return_value = outer, prior_return
        if start != self.epoch:
            self.invalidate(may_run_user=True)
            return Value()
        if raised:
            self.state.raised = raised
        return result

    @staticmethod
    def local_names(statements):
        names = set()
        def scan(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
                return
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            for child in ast.iter_child_nodes(node):
                scan(child)
        for statement in statements:
            scan(statement)
        return names

    @staticmethod
    def is_generator(function):
        def scan(node):
            if isinstance(node, (ast.Yield, ast.YieldFrom)):
                return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                return False
            return any(scan(child) for child in ast.iter_child_nodes(node))
        return any(scan(statement) for statement in function.body)


def analyze_literals(code: str, tree: ast.Module) -> LiteralAnalysis:
    result = LiteralAnalysis(code)
    result.suite(tree.body)
    if result.builtin_uses:
        result.note('、'.join(sorted(result.builtin_uses)) + ' にはbuiltins（組み込み名）としての参照があります。')
    return result
