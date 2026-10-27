"""実行とアプリ解析を別プロセスで行う。これはOSのセキュリティsandboxではない。

実行対象は制限された教育用コードのみ。拒否されたコードは実行せず記録する。
アプリ解析もタイムアウトで区切り、1ケースの失敗が全体を止めないようにする。
"""
import ast
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


MAX_CODE = 100_000
MAX_OUTPUT = 100_000
STDIN_FIXTURE = '20\n' * 16
# 標準の数学・純粋計算だけを許す。ネットワーク、プロセス起動、任意importは禁止。
SAFE_MODULES = {'math'}
FORBIDDEN_NAMES = {'eval', 'exec', 'compile', 'globals', 'locals', 'vars', 'getattr',
                   'setattr', 'delattr', 'type', 'object', 'help', 'breakpoint', 'exit', 'quit'}
SAFE_CALLS = {'print', 'input', 'int', 'float', 'str', 'bool', 'len', 'range', 'list',
              'tuple', 'dict', 'set', 'iter', 'next', 'sum', 'min', 'max', 'abs',
              'round', 'enumerate', 'zip', 'sorted', 'reversed', 'open', 'sqrt',
              'pow', 'AssertionError', 'ValueError', 'TypeError', 'RuntimeError'}
SAFE_METHODS = {'append', 'remove', 'pop', 'clear', 'upper', 'lower',
                'strip', 'split', 'join', 'decode', 'encode', 'read', 'sqrt',
                'keys', 'values', 'items', 'get', 'copy', 'update', 'count', 'index'}


def execution_policy(code: str) -> str | None:
    """保守的な事前チェック。許可しない入力は評価器の制約として扱う。

    構文エラーは実行前のcompile段階で停止するので許可する。
    ユーザー定義の純粋関数・クラスは許すが、特殊属性や動的コード生成は拒否する。
    """
    if len(code) > MAX_CODE:
        return 'code size limit'
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    except (ValueError, RecursionError, MemoryError) as exc:
        return f'preflight parse: {type(exc).__name__}'
    nodes = list(ast.walk(tree))
    if len(nodes) > 20_000:
        return 'AST size limit'
    call_names = set(SAFE_CALLS)
    defined_classes = {node.name for node in nodes if isinstance(node, ast.ClassDef)}
    call_names.update(defined_classes)
    call_names.update(node.name for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    direct_open_nodes = {id(node.func) for node in nodes if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name) and node.func.id == 'open'}
    # 未知のメソッド名も、単一束縛の組み込みリテラルで属性が存在しないと
    # 確認できれば許可する。特定のタイプミス文字列を許可リストに足さない。
    # これは実行ポリシー専用で、アプリの診断スコアには利用しない。
    bindings = {}
    literal_types = {}
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bindings[node.id] = bindings.get(node.id, 0) + 1
        elif isinstance(node, ast.arg):
            bindings[node.arg] = bindings.get(node.arg, 0) + 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] = bindings.get(node.name, 0) + 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                identifier = alias.asname or alias.name.split('.')[0]
                bindings[identifier] = bindings.get(identifier, 0) + 1
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value_type = type(node.value.value) if isinstance(node.value, ast.Constant) else {
                ast.List: list, ast.Tuple: tuple, ast.Dict: dict, ast.Set: set}.get(type(node.value))
            if value_type in {str, bytes, int, float, bool, list, tuple, dict, set, type(None)}:
                literal_types[node.targets[0].id] = value_type
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.decorator_list:
                return 'decorators not allowed'
            if node.name.startswith('__') and node.name != '__init__':
                return 'special methods not allowed'
            if isinstance(node, ast.ClassDef) and (node.bases or node.keywords):
                return 'class inheritance/metaclass not allowed'
        if isinstance(node, (ast.Lambda, ast.Global, ast.Nonlocal)):
            return 'dynamic binding not allowed'
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            return 'special names not allowed'
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return 'dynamic/introspection names not allowed'
        if isinstance(node, ast.Name) and node.id == 'open' and id(node) not in direct_open_nodes:
            return 'open aliases not allowed'
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            return 'special attributes not allowed'
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [item.name for item in node.names] if isinstance(node, ast.Import) else [node.module or '']
            if isinstance(node, ast.ImportFrom) and (node.level or any(item.name == '*' for item in node.names)):
                return 'relative/wildcard import not allowed'
            if isinstance(node, ast.ImportFrom) and any(item.name.startswith('_') for item in node.names):
                return 'private import names not allowed'
            for module in modules:
                # 存在しないトップレベル名はimportlibの検索だけで失敗する。
                # specが見つかった未知モジュールは実行しない（site-packagesも無効）。
                if '.' in module or not module.isidentifier() or module.startswith('_'):
                    return 'only simple module names allowed'
                if module not in SAFE_MODULES:
                    import importlib.machinery
                    spec = importlib.machinery.PathFinder.find_spec(module, [p for p in sys.path if p and 'site-packages' not in p and Path(p).resolve() != Path.cwd()])
                    if module in sys.builtin_module_names or spec is not None:
                        return f'module is not allowed: {module}'
            if isinstance(node, ast.ImportFrom):
                call_names.update(item.asname or item.name for item in node.names)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in call_names:
                    return f'call is not allowed: {node.func.id}'
                if node.func.id == 'open':
                    # 読み取りも、一時作業フォルダ直下の単純なファイル名に限定する。
                    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                        return 'open requires literal filename'
                    filename = node.args[0].value
                    if not filename or any(char in filename for char in '/\\:') or filename.casefold() in {'.', '..', 'snippet.py'}:
                        return 'open path outside temporary directory'
                    if re.match(r'(?i)^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', filename):
                        return 'device filename not allowed'
                    mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == 'mode'), None)
                    if mode and (not isinstance(mode, ast.Constant) or mode.value not in {'r', 'rt', 'rb'}):
                        return 'open write mode not allowed'
                    if any(k.arg not in {'mode', 'encoding', 'errors', 'newline'} for k in node.keywords):
                        return 'open custom arguments not allowed'
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr not in SAFE_METHODS:
                    receiver = node.func.value
                    receiver_type = literal_types.get(receiver.id) if isinstance(receiver, ast.Name) and bindings.get(receiver.id) == 1 else None
                    if receiver_type is None or hasattr(receiver_type, node.func.attr):
                        return f'method is not allowed: {node.func.attr}'
            else:
                return 'indirect calls not allowed'
    return None


def child_environment(directory: str) -> dict[str, str]:
    result = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result.update(TEMP=directory, TMP=directory, PYTHONIOENCODING='utf-8')
    return result


def execute_code(code: str, timeout: float) -> dict:
    rejected = execution_policy(code)
    if rejected:
        return {'status': 'rejected', 'reason': rejected, 'stderr': '', 'stdout': ''}
    with tempfile.TemporaryDirectory(prefix='python-error-eval-') as temporary:
        script = Path(temporary) / 'snippet.py'
        script.write_text(code, encoding='utf-8')
        try:
            # -I: PYTHONPATH/user siteを無視。-S: site-packagesを読み込まない。
            # -X utf8: Windowsの日本語ログもUTF-8で保存する。
            with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
                process = subprocess.Popen([sys.executable, '-I', '-S', '-X', 'utf8', str(script)],
                                           cwd=temporary, env=child_environment(temporary),
                                           stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file)
                try:
                    process.stdin.write(STDIN_FIXTURE.encode('utf-8'))
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                deadline = time.monotonic() + timeout
                aborted = None
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        aborted = ('timeout', f'execution exceeded {timeout}s')
                    elif max(os.fstat(stdout_file.fileno()).st_size, os.fstat(stderr_file.fileno()).st_size) > MAX_OUTPUT:
                        aborted = ('output_limit', f'output exceeded {MAX_OUTPUT} bytes')
                    if aborted:
                        process.kill()
                        break
                    time.sleep(0.01)
                process.wait(timeout=2)
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read(MAX_OUTPUT + 1).decode('utf-8', 'replace')
                stderr = stderr_file.read(MAX_OUTPUT + 1).decode('utf-8', 'replace')
                if aborted:
                    return {'status': aborted[0], 'reason': aborted[1], 'stderr': '', 'stdout': stdout[:MAX_OUTPUT]}
        except OSError as exc:
            return {'status': 'execution_failed', 'reason': repr(exc), 'stderr': '', 'stdout': ''}
        stderr = stderr.replace(str(script), '<evaluation>/snippet.py')
        exception = None
        # Ground truthをアプリのparserから独立に取る。CPythonの最後の例外行だけ読む。
        for line in reversed(stderr.splitlines()):
            match = re.fullmatch(r'([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?::.*)?', line.strip())
            if match and (match[1].endswith(('Error', 'Exception')) or match[1] in {'StopIteration', 'SystemExit', 'KeyboardInterrupt', 'GeneratorExit'}):
                exception = match[1].rsplit('.', 1)[-1]
                break
        return {'status': 'completed', 'returncode': process.returncode,
                'execution': 'no_error' if process.returncode == 0 else 'error',
                'exception_type': exception, 'stdout': stdout[:MAX_OUTPUT],
                'stderr': stderr[:MAX_OUTPUT], 'output_truncated': max(len(stderr), len(stdout)) > MAX_OUTPUT}


def analyze_in_child(project: Path, code: str, log: str, timeout: float) -> dict:
    """アプリの公開pipelineを、正解ラベルを渡さずに呼び出す。"""
    with tempfile.TemporaryDirectory(prefix='python-analysis-eval-') as temporary:
        source = Path(__file__).resolve()
        try:
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(source), '--worker', str(project)],
                                    input=json.dumps({'code': code, 'log': log}),
                                    cwd=temporary, env=child_environment(temporary), text=True,
                                    encoding='utf-8', errors='replace', capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'reason': f'analysis exceeded {timeout}s'}
        if result.returncode:
            return {'status': 'crashed', 'reason': result.stderr[-4000:], 'returncode': result.returncode}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {'status': 'crashed', 'reason': 'analysis worker returned invalid JSON', 'stderr': result.stderr[-4000:]}


def worker(project: Path) -> None:
    sys.path.insert(0, str(project))
    from src.analyzer import analyze_error
    from src.code_analysis import analyze_code
    request = json.load(sys.stdin)
    try:
        output = analyze_error(request['log'], request['code'])
        # コードだけの事前警告と、ログを使って対応付けるfindingsを分離する。
        static = analyze_code(request['code'])
        print(json.dumps({'status': 'returned', 'pipeline': asdict(output), 'static': asdict(static)}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'status': 'crashed', 'reason': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]).resolve())
    else:
        raise SystemExit('Use evaluate.py, not runner.py directly.')
