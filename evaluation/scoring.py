"""説明可能な意味判定。ID・タイトル・入力コードの完全一致を一切使わない。

期待文を一般的な概念に変換し、アプリが実際に返した構造化事実・文章のみ照合する。
入力コードから評価器が新しい原因を推論し、それをアプリの正答として加点しない。
未対応の期待文はunmappedにし、合格にはしない（評価器の制限として表示）。
"""
import re


ACTIONABLE = {'undefined_name', 'use_before_definition', 'possibly_unbound', 'index_out_of_range',
              'incompatible_operation', 'missing_attribute', 'invalid_index_type', 'missing_key',
              'unhashable_key', 'zero_division', 'invalid_conversion', 'call_arguments'}
SYNTAX_DIAGNOSTIC = re.compile(r"expected ['\"]:|invalid syntax|never closed|unterminated|indented block|unexpected indent", re.I)


def warning(analysis: dict) -> bool:
    return any(f['kind'] in ACTIONABLE for f in analysis.get('findings', [])) or (
        analysis.get('status') == 'unavailable' and any(SYNTAX_DIAGNOSTIC.search(note) for note in analysis.get('notes', [])))


def identifiers(text: str) -> list[str]:
    return re.findall(r'[A-Za-z_]\w*', text)


# 上から、具体的な概念→広い概念の順。固有の変数名やケース番号は含まない。
RULES = [
    (r'複数.*類似', 'multiple_similar'),
    (r'一部の経路', 'conditional_binding'),
    (r'ループが一度も', 'empty_loop_binding'),
    (r'builtins', 'builtin_resolution'),
    (r'import 済み', 'imported_binding'),
    (r'別スコープ', 'separate_scopes'),
    (r'except で処理', 'handled_exception'),
    (r'ローカル変数', 'local_binding'),
    (r'使用時点.*未定義|代入前に参照', 'before_definition'),
    (r'後続行.*代入', 'later_definition'),
    (r'類似候補', 'similar_name'),
    (r'未定義', 'undefined_name'),
    (r'長さは\d+', 'sequence_length'),
    (r'範囲外', 'out_of_range'),
    (r'から.*import', 'import_from'),
    (r'import 対象', 'import_target'),
    (r'属性.*ない|[A-Za-z_]\w* に [A-Za-z_]\w* がない', 'missing_attribute'),
    (r'属性は存在', 'present_attribute'),
    (r'が None', 'none_binding'),
    (r'不正な加算', 'mixed_addition'),
    (r'input.*戻り値.*文字列', 'input_string'),
    (r'数値変換.*必要', 'numeric_conversion'),
    (r'辞書.*キー.*存在しない', 'missing_key'),
    (r'0.*除算', 'zero_division'),
    (r'ファイルパス.*確認', 'file_path_check'),
    (r'整数に変換できない', 'invalid_integer'),
    (r'if 文.*構文', 'if_syntax'),
    (r'コロン不足', 'missing_colon'),
    (r'括弧.*閉じられていない', 'unclosed_parenthesis'),
    (r'インデント不足', 'missing_indent'),
    (r'追加インデント', 'extra_indent'),
    (r'条件式で =', 'assignment_in_condition'),
    (r'==.*可能性', 'comparison_candidate'),
    (r'文字列リテラル.*閉じられていない', 'unclosed_string'),
    (r'\d+引数必要', 'required_argument_count'),
    (r'\d+引数しか', 'supplied_argument_count'),
    (r'多い位置引数', 'too_many_arguments'),
    (r'引数.*定義されていない', 'unknown_keyword'),
    (r'大小比較', 'mixed_comparison'),
    (r'再帰.*終了条件', 'unbounded_recursion'),
    (r'空のイテレータ.*next', 'empty_iterator'),
    (r'assert.*False', 'false_assertion'),
    (r'辞書.*走査.*サイズ変更', 'dict_iteration_mutation'),
    (r'set.*走査.*サイズ変更', 'set_iteration_mutation'),
    (r'UTF-8.*不正', 'invalid_utf8'),
    (r'bytes.*str.*混在', 'mixed_bytes_string'),
    (r'添字.*float', 'float_index'),
    (r'list.*辞書キー', 'unhashable_list_key'),
]


def concept(expectation: str) -> str | None:
    return next((name for pattern, name in RULES if re.search(pattern, expectation)), None)


def prose(pipeline: dict, ast_only: bool) -> list[str]:
    analysis = pipeline.get('code_analysis') or {}
    result = [f['message'] for f in analysis.get('findings', [])] + list(analysis.get('notes', []))
    if not ast_only:
        explanation = pipeline.get('explanation', {})
        result += [explanation.get('summary', ''), explanation.get('cause', ''), *explanation.get('checkpoints', [])]
        result += pipeline.get('hints', [])
    # error.message、code_context、finding.evidence、fix_exampleは診断文章ではない。
    return [item for item in result if item]


def check_detection(expectation: str, pipeline: dict, *, ast_only: bool) -> dict:
    name = concept(expectation)
    check = {'expectation': expectation, 'concept': name, 'matched': False, 'evidence': [], 'status': 'missing'}
    if name is None:
        check['status'] = 'unmapped'
        return check
    analysis = pipeline.get('code_analysis') or {}
    findings = analysis.get('findings', [])
    definitions = analysis.get('definitions', [])
    ids = identifiers(expectation)
    texts = prose(pipeline, ast_only)

    def take(items):
        check['evidence'].extend(items)

    def found(kind, target=None):
        return [f for f in findings if f['kind'] == kind and (target is None or f.get('target') == target)]

    def text_match(pattern, required=()):
        # 一つの診断文で概念と対象を結び付ける。別の一般例は正答にしない。
        return [t for t in texts if re.search(pattern, t, re.I) and all(re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', t) for token in required)]

    if name == 'undefined_name':
        take(found('undefined_name', ids[0] if ids else None))
    elif name == 'before_definition':
        take(found('use_before_definition', ids[0] if ids else None))
    elif name == 'later_definition':
        target = ids[0] if ids else None
        take([{'use': f, 'definition': d} for f in found('use_before_definition', target)
              for d in definitions if d['name'] == f['target'] and d['line'] > f['line']
              and any(u['name'] == f['target'] and u['line'] == f['line'] and u['scope'] == d['scope'] for u in analysis.get('uses', []))])
    elif name in {'similar_name', 'multiple_similar'}:
        for f in found('similar_name'):
            candidates = f.get('related_names', [])
            if (name == 'multiple_similar' and len(candidates) >= 2) or (name == 'similar_name' and all(i in candidates for i in ids)):
                take([f])
    elif name == 'local_binding':
        target = ids[0] if ids else None
        function_scopes = {f"{d['name']}@{d['line']}" for d in definitions if d['kind'] == 'function'}
        take([d for d in definitions if d['name'] == target and d['scope'] in function_scopes
              and any(u['name'] == target and u['scope'] == d['scope'] for u in analysis.get('uses', []))])
    elif name == 'separate_scopes':
        for identifier in set(ids):
            matches = [d for d in definitions if d['name'] == identifier]
            scopes = {d['scope'] for d in matches}
            if len(scopes) >= 2 and any(scope.startswith('top@') for scope in scopes):
                take(matches)
    elif name in {'imported_binding', 'import_target', 'import_from'}:
        wanted = [i for i in ids if i != 'import']
        for item in analysis.get('imports', []):
            exported = {item['module'], item.get('imported_name'), item.get('bound_name')}
            if all(i in exported for i in wanted):
                take([item])
    elif name in {'sequence_length', 'out_of_range'}:
        for f in found('index_out_of_range'):
            numbers = re.findall(r'\d+', expectation)
            position = 0 if name == 'sequence_length' else 1
            target_ok = not ids or ids[0] == 'index' or f['target'].startswith(ids[0] + '[')
            if target_ok and (not numbers or numbers[0] == f['related_names'][position]):
                take([f])
    elif name == 'missing_attribute':
        # object.attribute位置の発見を、型・属性の有無の診断としては加点しない。
        take(text_match(r'属性.*(ありません|ない|存在しな|持っていな)', ids))
    elif name == 'present_attribute':
        take(text_match(r'属性.*(存在|定義.*あり|持って)', ids))
    elif name == 'none_binding':
        take(text_match(r'(?:が|は|=|：).*None', ids))
    elif name == 'input_string':
        take(text_match(r'input.*(?:結果|戻り値).*文字列'))
    elif name == 'numeric_conversion':
        take(text_match(r'数値.*変換|変換.*数値'))
    elif name == 'missing_key':
        take(text_match(r'(?:キー.*ありません|キー.*存在しな)', ids))
    elif name == 'zero_division':
        take(text_match(r'0.*(?:割ろう|除算|割って)'))
    elif name == 'file_path_check':
        take(text_match(r'(?:ファイル名|パス|作業フォルダ).*(?:確認|違う)'))
    elif name == 'invalid_integer':
        take(text_match(r'整数.*(?:読めな|変換できな)|(?:読めな|変換できな).*整数', ids))
    elif name == 'missing_colon':
        take(text_match(r"expected ['\"]:|コロン.*不足|末尾.*:.*確認"))
    elif name == 'unclosed_parenthesis':
        take(text_match(r'never closed|括弧.*閉じ.*(?:ない|確認)'))
    elif name == 'missing_indent':
        take(text_match(r"indented block after ['\"]if|if.*(?:字下げ|インデント)"))
    elif name == 'extra_indent':
        take(text_match(r'unexpected indent|(?:不要|余分).*インデント'))
    elif name == 'unclosed_string':
        take(text_match(r'unterminated string|(?:文字列|引用符).*閉じ.*(?:ない|確認)'))
    elif name == 'comparison_candidate':
        take(text_match(r"meant ['\"]==|==.*(?:可能性|確認|かもしれ)"))
    else:
        # 以下は現在の出力に無くても、将来一般的な診断文があれば照合できる。
        patterns = {
            'builtin_resolution': r'(?:builtins|組み込み)',
            'conditional_binding': r'(?:一部|すべてではない|特定).*経路|分岐.*(?:未定義|代入されな)',
            'empty_loop_binding': r'ループ.*(?:一度も|0回|未実行|空).*未定義',
            'handled_exception': r'except.*(?:処理|捕捉|キャッチ)',
            'mixed_addition': r'(?:加算|足し算|\+).*(?:できな|不正|合わな)|(?:不正|できな).*加算',
            'if_syntax': r'if.*(?:構文エラー|文法エラー|文法が不正)',
            'assignment_in_condition': r'条件(?:式)?.*(?:代入|(?<!=)=(?!=))',
            'required_argument_count': r'\d+.*引数.*(?:必要|受け取)',
            'supplied_argument_count': r'\d+.*引数.*(?:渡|指定|しか)',
            'too_many_arguments': r'位置引数.*(?:多|超)|(?:多すぎ|余分).*引数',
            'unknown_keyword': r'引数.*(?:定義されていな|存在しな|未対応)',
            'mixed_comparison': r'(?:大小|比較).*(?:できな|不正|合わな)',
            'unbounded_recursion': r'再帰.*(?:終了条件|停止条件|無限|終わらな)',
            'empty_iterator': r'空.*イテレータ.*next|next.*空.*イテレータ',
            'false_assertion': r'assert.*(?:False|偽|満たさな)',
            'dict_iteration_mutation': r'辞書.*(?:走査|反復|ループ).*(?:変更|削除)',
            'set_iteration_mutation': r'(?:set|集合).*(?:走査|反復|ループ).*(?:変更|削除)',
            'invalid_utf8': r'UTF-8.*(?:不正|読めな|復号できな)',
            'mixed_bytes_string': r'(?:混在|混合|連結できな|種類が異な)',
            'float_index': r'(?:添字|インデックス|位置番号).*float',
            'unhashable_list_key': r'(?:list|リスト).*(?:辞書キー|キー).*(?:使えな|できな|不可)',
        }
        # 名称・型・数字まで同じ文に含まれる必要がある。
        required = ids + (re.findall(r'\d+', expectation) if name in {'required_argument_count', 'supplied_argument_count'} else [])
        take(text_match(patterns[name], required))
    if check['evidence']:
        check.update(matched=True, status='matched')
    return check


def check_prohibited(expectation: str, pipeline: dict) -> dict:
    """候補と断定を区別する。辞書のdefinitionsに名前があるだけで「必ず安全」としない。"""
    analysis = pipeline.get('code_analysis') or {}
    ids = identifiers(expectation)
    evidence = []
    rule = 'unsupported'
    if '未定義' in expectation and 'グローバル' not in expectation:
        rule = 'wrong_undefined_warning'
        evidence = [f for f in analysis.get('findings', []) if f['kind'] in {'undefined_name', 'use_before_definition', 'possibly_unbound'}
                    and f.get('target') in ids]
    elif 'スコープエラー' in expectation:
        rule = 'wrong_scope_warning'
        evidence = [f for f in analysis.get('findings', []) if f['kind'] in {'undefined_name', 'use_before_definition', 'possibly_unbound'}]
    elif 'グローバル変数未定義' in expectation:
        rule = 'local_misdiagnosed_as_global'
        evidence = [t for t in prose(pipeline, False) if re.search(r'グローバル.*未定義', t) and not re.search(r'では(?:ない|ありません)', t)]
    elif '停止する' in expectation:
        rule = 'handled_exception_misdiagnosed_as_fatal'
        evidence = [t for t in prose(pipeline, False) if all(i in t for i in ids) and re.search(r'停止(?:する|します)|終了(?:する|します)', t)]
    elif re.search(r'確実|必ず|常に|正解|安全|定義済み', expectation):
        rule = 'unsupported_certainty'
        for text in prose(pipeline, False):
            if not re.search(r'確実|必ず|常に|唯一|正解|安全|必ず定義', text):
                continue
            if re.search(r'断定できません|とは限りません|候補|可能性|自分で確認', text):
                continue
            if not ids or all(i in text for i in ids):
                evidence.append(text)
    return {'expectation': expectation, 'rule': rule, 'violated': bool(evidence),
            'evidence': evidence, 'status': 'unmapped' if rule == 'unsupported' else 'checked',
            'limitation': '日本語の規則照合であり、任意の言い換え・否定を完全には扱えない。baselineは別途全文監査する。'}


FAILURE_CLASSES = {
    'conditional_binding': ('control flow解析不足', 'ツール側を改善可能'),
    'empty_loop_binding': ('control flow解析不足', 'ツール側を改善可能'),
    'local_binding': ('スコープ解析不足', 'ツール側を改善可能'),
    'builtin_resolution': ('評価器側の限界', '正しい無警告を確認済み・明示的な診断出力がない'),
    'handled_exception': ('control flow解析不足', 'ツール側を改善可能'),
    'separate_scopes': ('スコープ解析不足', 'ツール側を改善可能'),
    'unbounded_recursion': ('未対応エラー', '一般には静的判定困難・この単純例は改善可能'),
    'missing_attribute': ('型推論不足', '一般には静的判定困難・リテラルや単純クラスは改善可能'),
    'present_attribute': ('型推論不足', '一般には静的判定困難・単純クラスは改善可能'),
    'none_binding': ('型推論不足', 'ツール側を改善可能'),
    'if_syntax': ('ログparser／説明の問題', 'AST生成不能・ログ診断の具体化は改善可能'),
    'assignment_in_condition': ('ログparser／説明の問題', 'AST生成不能・ログ診断の具体化は改善可能'),
}


def failure_classification(check: dict) -> tuple[str, str]:
    name = check['concept']
    if check['status'] == 'unmapped':
        return '評価器側の限界', '手動確認が必要'
    if name in FAILURE_CLASSES:
        return FAILURE_CLASSES[name]
    if name in {'mixed_addition', 'input_string', 'numeric_conversion', 'mixed_comparison', 'mixed_bytes_string', 'float_index', 'unhashable_list_key'}:
        return '型推論不足', '一般には静的判定困難・この定数例は改善可能'
    if name in {'required_argument_count', 'supplied_argument_count', 'too_many_arguments', 'unknown_keyword'}:
        return 'AST解析の問題', '一般には動的呼び出しが困難・この直接呼び出しは改善可能'
    if name in {'empty_iterator', 'false_assertion', 'dict_iteration_mutation', 'set_iteration_mutation', 'invalid_utf8'}:
        return '未対応エラー', 'ツール側を改善可能'
    return 'AST解析の問題', 'ツール側を改善可能'
