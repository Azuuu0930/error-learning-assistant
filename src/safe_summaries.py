"""Small syntactic proofs for the literal pass; never execute pasted code.

Unsupported syntax fails closed. These are intentionally smaller than Python's
pure functions/classes; the caller still checks values, trust, and exceptions.
"""
import ast
from dataclasses import dataclass


SCALARS = {'int', 'float', 'bool', 'str', 'bytes', 'NoneType'}


def simple_expression(node, names):
    if isinstance(node, ast.Constant):
        return type(node.value).__name__ in SCALARS
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(simple_expression(item, names) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(key is not None and simple_expression(key, names)
                   and simple_expression(value, names) for key, value in zip(node.keys, node.values))
    # Only addition is summarized initially: other operators can have exceptions
    # the old pass does not yet model completely (negative powers, huge repeats).
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return simple_expression(node.left, names) and simple_expression(node.right, names)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Not)):
        return simple_expression(node.operand, names)
    return False


def plain_signature(function):
    args = function.args
    return (isinstance(function, ast.FunctionDef) and not function.decorator_list
            and not function.returns and not args.vararg and not args.kwarg
            and not any(a.annotation for a in [*args.posonlyargs, *args.args, *args.kwonlyargs])
            and all(isinstance(d, ast.Constant) and type(d.value).__name__ in SCALARS
                    for d in [*args.defaults, *args.kw_defaults] if d is not None))


def pure_function(function):
    if not plain_signature(function) or not 1 <= len(function.body) <= 16:
        return False
    if sum(1 for _ in ast.walk(function)) > 160:
        return False
    names = {a.arg for a in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
    for index, statement in enumerate(function.body):
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            if not simple_expression(statement.value, names):
                return False
            names.add(statement.targets[0].id)
        elif isinstance(statement, ast.Return) and index == len(function.body) - 1:
            return statement.value is None or simple_expression(statement.value, names)
        else:
            return False
    return False


@dataclass(frozen=True)
class SimpleClass:
    name: str
    initializer: ast.FunctionDef | None
    attributes: tuple[tuple[str, int], ...]


def simple_class(node):
    if node.bases or node.keywords or node.decorator_list or getattr(node, 'type_params', ()):
        return None
    initializer = None
    attributes = []
    if sum(1 for _ in ast.walk(node)) > 160:
        return None
    for statement in node.body:
        if isinstance(statement, ast.Pass) or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)):
            continue
        if not isinstance(statement, ast.FunctionDef) or statement.name != '__init__' or initializer is not None or not plain_signature(statement):
            return None
        initializer = statement
        positional = [*statement.args.posonlyargs, *statement.args.args]
        if not positional:
            return None
        self_name = positional[0].arg
        names = {a.arg for a in [*positional, *statement.args.kwonlyargs]} - {self_name}
        for instruction in statement.body:
            if isinstance(instruction, ast.Pass) or (isinstance(instruction, ast.Expr) and isinstance(instruction.value, ast.Constant) and isinstance(instruction.value.value, str)):
                continue
            if not (isinstance(instruction, ast.Assign) and len(instruction.targets) == 1):
                return None
            target = instruction.targets[0]
            # Store only literals or parameter references: no callbacks, dynamic
            # descriptors, expressions that could fail, or __class__ rewrites.
            if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                    and target.value.id == self_name and not target.attr.startswith('__')
                    and (isinstance(instruction.value, ast.Name) and instruction.value.id in names
                         or isinstance(instruction.value, ast.Constant) and type(instruction.value.value).__name__ in SCALARS)):
                return None
            attributes.append((target.attr, target.lineno))
    return SimpleClass(node.name, initializer, tuple(attributes))


def direct_iteration_mutation(loop, value):
    """Prove a size change followed by the next iteration, on a direct container.

Only one direct mutation and optional pass/continue are accepted. Any branch,
break, callback, additional write, or alias needs a fuller CFG and is skipped.
"""
    if not (isinstance(loop.iter, ast.Name) and isinstance(loop.target, ast.Name)
            and loop.target.id != loop.iter.id and value.kind in {'dict', 'set'}
            and value.length and value.keys is not None
            and (value.kind != 'dict' or value.safe_contents)):
        return None
    receiver, iterator_name = loop.iter.id, loop.target.id
    mutation = None
    for position, statement in enumerate(loop.body):
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Continue) and position == len(loop.body) - 1:
            return mutation
        if mutation is not None:
            return None
        member = None
        deleting = False
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and value.kind == 'dict':
            target = statement.targets[0]
            if not isinstance(statement.value, ast.Constant) or type(statement.value.value).__name__ not in SCALARS:
                return None
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == receiver:
                member = target.slice
        elif isinstance(statement, ast.Delete) and len(statement.targets) == 1 and value.kind == 'dict':
            target = statement.targets[0]
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == receiver:
                member, deleting = target.slice, True
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == receiver and not call.keywords):
                return None
            name = call.func.attr
            if name == 'clear' and not call.args or value.kind == 'dict' and name == 'popitem' and not call.args:
                mutation = call
                continue
            if len(call.args) == 1 and (value.kind == 'set' and name in {'add', 'remove', 'discard'} or value.kind == 'dict' and name == 'pop'):
                member, deleting = call.args[0], name != 'add'
        if member is None:
            return None
        if isinstance(member, ast.Name) and member.id == iterator_name:
            present = True
        elif isinstance(member, ast.Constant) and type(member.value).__name__ in SCALARS:
            present = member.value in value.keys
        else:
            return None
        if present != deleting:
            return None  # no size change, or deletion raises before advancing
        mutation = statement
    return mutation
