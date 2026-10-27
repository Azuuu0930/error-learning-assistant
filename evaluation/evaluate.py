"""Run: python evaluation/evaluate.py --execute-reviewed

コード実行は明示的なopt-in。添付42件の内容を確認したうえで使用する。
アプリにはcodeと実測stderrだけを渡し、expectedを渡さない。
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from evaluation.runner import analyze_in_child, execute_code, STDIN_FIXTURE
from evaluation.scoring import check_detection, check_prohibited, failure_classification, warning


def load_dataset(path: Path) -> tuple[dict, list[dict]]:
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.jsonl':
        cases = [json.loads(line) for line in text.splitlines() if line.strip()]
        metadata = {'dataset_name': path.stem, 'format': 'jsonl'}
    else:
        data = json.loads(text)
        if isinstance(data, list):
            cases, metadata = data, {'dataset_name': path.stem}
        else:
            cases = data['cases']
            metadata = {k: v for k, v in data.items() if k != 'cases'}
            if 'num_cases' in data and data['num_cases'] != len(cases):
                raise ValueError('num_cases does not match actual case count')
    ids = []
    for case in cases:
        if not isinstance(case.get('code'), str) or not isinstance(case.get('expected'), dict):
            raise ValueError('case requires code and expected')
        ids.append(case['id'])
        expected_warn(case)  # warnラベルの矛盾を読み込み時に検出する。
        if case['expected'].get('execution') not in {'error', 'no_error'}:
            raise ValueError('expected.execution must be error or no_error')
        if case['expected']['execution'] == 'error' and not case['expected'].get('exception_type'):
            raise ValueError('error case requires expected.exception_type')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate IDs')
    return metadata, cases


def expected_warn(case: dict) -> bool:
    expected = case['expected']
    analysis = case.get('analysis_expectations', {})
    if 'should_warn' in expected and 'should_warn' in analysis and expected['should_warn'] != analysis['should_warn']:
        raise ValueError('conflicting should_warn fields')
    value = analysis.get('should_warn', expected.get('should_warn', expected['execution'] == 'error'))
    if not isinstance(value, bool):
        raise ValueError('should_warn must be boolean')
    return value


def baseline_changed(manifest: dict, project: Path = PROJECT) -> list[str]:
    changed = []
    for relative, expected_hash in manifest['files'].items():
        path = project / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            changed.append(relative)
    source_set = {'app.py', *('src/' + p.name for p in (project / 'src').glob('*.py'))}
    changed.extend(sorted(source_set - set(manifest['files'])))
    return changed


def evaluate_case(case: dict, *, timeout: float, analysis_timeout: float, project: Path = PROJECT, scoring: str = 'legacy') -> dict:
    if scoring == 'structured':
        from evaluation.structured_scoring import check_detection as detect, warning as warns
    elif scoring == 'legacy':
        detect, warns = check_detection, warning
    else:
        raise ValueError('scoring must be legacy or structured')
    code = case['code']
    expected = case['expected']
    expectations = case.get('analysis_expectations', {})
    reasons = []
    classifications = []
    def fail(reason, category, disposition):
        reasons.append(reason)
        classifications.append({'category': category, 'disposition': disposition})
    try:
        ast.parse(code)
        ast_eligible = True
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        ast_eligible = False
    observed = execute_code(code, timeout)
    # タイムアウト/実行拒否でも静的解析の応答率は測る。正解ログを捏造しない。
    actual = analyze_in_child(project, code, observed.get('stderr', ''), analysis_timeout)
    returned = actual.get('status') == 'returned'
    runtime_validated = observed['status'] == 'completed' and observed.get('execution') == expected['execution'] and observed.get('exception_type') == expected.get('exception_type')
    if not runtime_validated:
        fail('実行環境・fixture・実行ポリシーで期待結果を再現できなかった。例外種評価は不正解扱い。', '評価器側の限界', '評価環境の確認が必要')
    if not returned:
        fail(f"アプリ解析失敗: {actual.get('reason', actual['status'])}", '解析クラッシュ', 'ツール側またはタイムアウト設定の確認が必要')
    pipeline = actual.get('pipeline', {})
    static = actual.get('static', {})
    predicted_type = pipeline.get('error', {}).get('error_type')
    error_type_correct = bool(returned and runtime_validated and predicted_type == expected.get('exception_type'))
    if expected['execution'] == 'error' and returned and runtime_validated and not error_type_correct:
        fail(f"例外種類: expected={expected.get('exception_type')}, actual={predicted_type}", 'ログparserの問題', 'ツール側を改善可能')
    static_warning = warns(static) if returned else None
    log_warning = bool(predicted_type or warns(pipeline.get('code_analysis') or {})) if returned else None
    static_correct = returned and static_warning == expected_warn(case)
    log_correct = returned and runtime_validated and log_warning == expected_warn(case)
    if not static_correct:
        environment_dependent = predicted_type in {'ModuleNotFoundError', 'ImportError', 'FileNotFoundError'}
        fail(f'コードだけの警告: expected={expected_warn(case)}, actual={static_warning}',
             '誤警告' if static_warning else ('静的解析の限界' if environment_dependent else 'AST解析の問題'),
             '実行環境に依存するためコードだけでの断定は不適切・ログ併用で確認' if environment_dependent else 'ツール側を改善可能')
    if not log_correct:
        fail('ログ併用のError/No-error判定が期待と異なる', '誤警告／ログparserの問題', 'ツール側を改善可能')
    ast_checks = [detect(text, pipeline, ast_only=True) for text in expectations.get('should_detect', [])]
    combined_checks = [detect(text, pipeline, ast_only=False) for text in expectations.get('should_detect', [])]
    prohibited = [check_prohibited(text, pipeline) for text in expectations.get('should_not_claim', [])]
    for check in combined_checks:
        if not check['matched']:
            category, disposition = failure_classification(check)
            fail(f"期待した診断が欠落: {check['expectation']} ({check['concept'] or 'unmapped'})", category, disposition)
    for check in prohibited:
        if check['status'] == 'unmapped':
            fail(f"禁止断定の照合規則が未対応: {check['expectation']}", '評価器側の限界', '手動確認が必要')
        elif check['violated']:
            fail(f"誤った主張: {check['expectation']}", '誤断定', 'ツール側を改善可能')
    expected_category = expected.get('primary_category')
    category_correct = None if expected_category is None else pipeline.get('error', {}).get('category') == expected_category
    if category_correct is False:
        fail('primary_categoryが一致しない（文字列分類の体系が異なる可能性あり）', '評価器側の限界', '分類体系の対応の確認が必要')
    preferred = expectations.get('preferred_confidence', case.get('preferred_confidence'))
    # 今回の原本にはpreferred_confidenceが無い。将来の未定義形式を黙って合格させない。
    if preferred is not None:
        fail('preferred_confidenceの形式が未規定のため自動採点していない', '評価器側の限界', '信頼度の期待schemaを明文化する必要がある')
    unique_classes = [dict(items) for items in dict.fromkeys(tuple(item.items()) for item in classifications)]
    return {
        'id': case['id'], 'title': case.get('title', ''), 'difficulty': case.get('difficulty', 'unknown'),
        'expected': expected, 'analysis_expectations': expectations,
        'runtime': observed, 'actual': actual,
        'checks': {'runtime_validated': runtime_validated, 'error_type_correct': error_type_correct,
                   'expected_warning': expected_warn(case),
                   'static_warning': static_warning, 'static_warning_correct': static_correct,
                   'log_assisted_warning': log_warning, 'log_assisted_warning_correct': log_correct,
                   'ast_eligible': ast_eligible, 'ast_diagnosis': ast_checks, 'combined_diagnosis': combined_checks,
                   'prohibited_claims': prohibited, 'category_correct': category_correct,
                   'preferred_confidence': preferred},
        'pass': not reasons, 'status': 'PASS' if not reasons else 'FAIL',
        'failure_reasons': reasons, 'failure_classification': unique_classes,
    }


def metric(numerator: int, denominator: int) -> dict:
    return {'numerator': numerator, 'denominator': denominator,
            'percent': round(100 * numerator / denominator, 2) if denominator else None}


def aggregate(results: list[dict]) -> dict:
    errors = [r for r in results if r['expected']['execution'] == 'error']
    normals = [r for r in results if r['expected']['execution'] == 'no_error']
    ast_cases = [r for r in results if r['checks']['ast_eligible'] and r['checks']['ast_diagnosis']]
    prohibited = [r for r in results if r['checks']['prohibited_claims']]
    all_ast_items = [c for r in ast_cases for c in r['checks']['ast_diagnosis']]
    all_combined_items = [c for r in results for c in r['checks']['combined_diagnosis']]
    return {
        'error_type_accuracy': metric(sum(r['checks']['error_type_correct'] for r in errors), len(errors)),
        'error_no_error_accuracy_static': metric(sum(r['checks']['static_warning_correct'] for r in results), len(results)),
        'error_no_error_accuracy_log_assisted': metric(sum(r['checks']['log_assisted_warning_correct'] for r in results), len(results)),
        'false_positive_rate': metric(sum(r['checks']['static_warning'] is True for r in normals), len(normals)),
        'normal_cases_unevaluable': sum(r['checks']['static_warning'] is None for r in normals),
        'ast_diagnosis_accuracy': metric(sum(r['actual']['status'] == 'returned' and all(c['matched'] for c in r['checks']['ast_diagnosis']) for r in ast_cases), len(ast_cases)),
        'ast_expectation_recall': metric(sum(c['matched'] for c in all_ast_items), len(all_ast_items)),
        'combined_diagnosis_accuracy': metric(sum(bool(r['checks']['combined_diagnosis']) and all(c['matched'] for c in r['checks']['combined_diagnosis']) for r in results), sum(bool(r['checks']['combined_diagnosis']) for r in results)),
        'combined_expectation_recall': metric(sum(c['matched'] for c in all_combined_items), len(all_combined_items)),
        'incorrect_claim_rate': metric(sum(any(c['violated'] for c in r['checks']['prohibited_claims']) for r in prohibited), len(prohibited)),
        'incorrect_claim_rate_all_cases': metric(sum(any(c['violated'] for c in r['checks']['prohibited_claims']) for r in results), len(results)),
        'coverage': metric(sum(r['actual']['status'] == 'returned' for r in results), len(results)),
        'strict_pass': metric(sum(r['pass'] for r in results), len(results)),
        'runtime_validated': metric(sum(r['checks']['runtime_validated'] for r in results), len(results)),
        'confusion_matrix_static': {
            'true_positive': sum(r['checks'].get('expected_warning', r['expected']['execution'] == 'error') and r['checks']['static_warning'] is True for r in results),
            'false_negative': sum(r['checks'].get('expected_warning', r['expected']['execution'] == 'error') and r['checks']['static_warning'] is False for r in results),
            'true_negative': sum(not r['checks'].get('expected_warning', r['expected']['execution'] == 'error') and r['checks']['static_warning'] is False for r in results),
            'false_positive': sum(not r['checks'].get('expected_warning', r['expected']['execution'] == 'error') and r['checks']['static_warning'] is True for r in results),
            'unevaluable': sum(r['checks']['static_warning'] is None for r in results)},
        'unmapped_detection_items': sum(c['status'] == 'unmapped' for c in all_combined_items),
        'unmapped_prohibited_items': sum(c['status'] == 'unmapped' for r in results for c in r['checks']['prohibited_claims']),
        'prohibited_items': sum(len(r['checks']['prohibited_claims']) for r in results),
        'confidence_labels': dict(Counter(f['confidence'] for r in results for f in (r['actual'].get('pipeline', {}).get('code_analysis') or {}).get('findings', []))),
    }


def formatted(value: dict) -> str:
    return 'N/A (0 cases)' if value['percent'] is None else f"{value['percent']:.2f}% ({value['numerator']}/{value['denominator']})"


def write_summary(report: dict, output: Path) -> None:
    metrics = report['metrics']
    lines = [f"# {report.get('version_label', 'Baseline')} evaluation", '', f"Evaluation Dataset: {len(report['cases'])} cases", '',
             f"Error Type Accuracy: {formatted(metrics['error_type_accuracy'])}",
             f"Error/No-Error Accuracy (code only): {formatted(metrics['error_no_error_accuracy_static'])}",
             f"Error/No-Error Accuracy (runtime log + code): {formatted(metrics['error_no_error_accuracy_log_assisted'])}",
             f"False Positive Rate: {formatted(metrics['false_positive_rate'])}",
             f"AST Diagnosis Accuracy (valid syntax, all requested facts): {formatted(metrics['ast_diagnosis_accuracy'])}",
             f"AST Expectation Recall (individual facts): {formatted(metrics['ast_expectation_recall'])}",
             f"Combined Diagnosis Accuracy (log explanations + AST): {formatted(metrics['combined_diagnosis_accuracy'])}",
             f"Incorrect Claim Rate (cases with prohibited claims): {formatted(metrics['incorrect_claim_rate'])}",
             f"Coverage: {metrics['coverage']['numerator']}/{metrics['coverage']['denominator']}",
             f"Strict PASS: {formatted(metrics['strict_pass'])}", '',
             'Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。',
             'ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。',
             'PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。',
             '禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。', '',
             '| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |',
             '|---|---:|---:|---:|---:|---:|']
    for difficulty, values in report['by_difficulty'].items():
        lines.append(f"| {difficulty} | {formatted(values['strict_pass'])} | {formatted(values['error_type_accuracy'])} | {formatted(values['error_no_error_accuracy_static'])} | {formatted(values['ast_diagnosis_accuracy'])} | {values['coverage']['numerator']}/{values['coverage']['denominator']} |")
    lines += ['', '## FAIL cases', '', '| ID | Title | Failure reasons |', '|---|---|---|']
    for result in report['cases']:
        if not result['pass']:
            reasons = '<br>'.join(result['failure_reasons']).replace('|', '\\|')
            lines.append(f"| {result['id']} | {result['title']} | {reasons} |")
    lines += ['', '## Failure classification (overlapping)', '', '| Category | Cases |', '|---|---:|']
    for category, count in report['failure_categories'].items():
        lines.append(f'| {category} | {count} |')
    lines += ['', f"Snapshot unchanged: {report['baseline']['unchanged']}",
              f"Runtime/dataset agreement: {formatted(metrics['runtime_validated'])}",
              f"Unmapped expectations: {metrics['unmapped_detection_items']}; unmapped prohibited claims: {metrics['unmapped_prohibited_items']}", '',
              'このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。', '']
    (output / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).with_name('python_error_evaluation_dataset.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--analysis-timeout', type=float, default=10.0)
    parser.add_argument('--execute-reviewed', action='store_true', help='Execute only code that has been reviewed and passes the restrictive policy')
    parser.add_argument('--project', type=Path, default=PROJECT, help='Application checkout to measure, independent of this evaluator')
    parser.add_argument('--allow-version-change', action='store_true', help='Measure an explicitly changed application; preserve original baseline files')
    parser.add_argument('--label', default='Baseline')
    parser.add_argument('--scoring', choices=('legacy', 'structured'), default='legacy', help='Keep original wording scoring or add explicit structured observations')
    arguments = parser.parse_args(argv)
    if not arguments.execute_reviewed:
        parser.error('内容を確認済みの教育用データセットに --execute-reviewed を指定してください。subprocessは完全なsandboxではありません。')
    if arguments.timeout <= 0 or arguments.analysis_timeout <= 0:
        parser.error('timeouts must be positive')
    evaluation = Path(__file__).resolve().parent
    application = arguments.project.resolve()
    manifest = json.loads((evaluation / 'baseline_manifest.json').read_text(encoding='utf-8'))
    changed_before = baseline_changed(manifest, application)
    if changed_before and not arguments.allow_version_change:
        raise SystemExit(f'Frozen baseline changed; evaluation refused: {changed_before}')
    metadata, cases = load_dataset(arguments.dataset)
    started = datetime.now(timezone.utc)
    method_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in evaluation.glob('*.py')}
    application_hashes = {str(p.relative_to(application)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [application / 'app.py', *sorted((application / 'src').glob('*.py'))]}
    results = []
    for position, case in enumerate(cases, 1):
        try:
            result = evaluate_case(case, timeout=arguments.timeout, analysis_timeout=arguments.analysis_timeout, project=application, scoring=arguments.scoring)
        except Exception as exc:
            # evaluator自体の予期しない失敗も記録し、後続ケースは継続する。
            result = {'id': case['id'], 'title': case.get('title', ''), 'difficulty': case.get('difficulty', 'unknown'),
                      'expected': case['expected'], 'analysis_expectations': case.get('analysis_expectations', {}),
                      'runtime': {'status': 'evaluator_crash'}, 'actual': {'status': 'evaluator_crash', 'reason': repr(exc)},
                      'checks': {'runtime_validated': False, 'error_type_correct': False, 'static_warning': None,
                                 'expected_warning': expected_warn(case),
                                 'static_warning_correct': False, 'log_assisted_warning': None, 'log_assisted_warning_correct': False,
                                 'ast_eligible': True, 'ast_diagnosis': [{'matched': False, 'status': 'missing'} for _ in case.get('analysis_expectations', {}).get('should_detect', [])],
                                 'combined_diagnosis': [{'matched': False, 'status': 'unmapped'} for _ in case.get('analysis_expectations', {}).get('should_detect', [])],
                                 'prohibited_claims': [{'violated': False, 'status': 'unmapped'} for _ in case.get('analysis_expectations', {}).get('should_not_claim', [])]},
                      'pass': False, 'status': 'FAIL', 'failure_reasons': [f'Evaluator crash: {exc}'],
                      'failure_classification': [{'category': '評価器側の限界', 'disposition': '評価器修正が必要'}]}
        results.append(result)
        print(f"{position}/{len(cases)} {result['id']}: {result['status']}", flush=True)
    changed_after = baseline_changed(manifest, application)
    application_unchanged = all(hashlib.sha256((application / name).read_bytes()).hexdigest() == digest for name, digest in application_hashes.items())
    report = {
        'schema_version': 1, 'version_label': arguments.label, 'started_at': started.isoformat(), 'completed_at': datetime.now(timezone.utc).isoformat(),
        'dataset': {**metadata, 'sha256': hashlib.sha256(arguments.dataset.read_bytes()).hexdigest()},
        'environment': {'python': sys.version, 'execution_timeout_seconds': arguments.timeout,
                        'analysis_timeout_seconds': arguments.analysis_timeout, 'stdin_fixture': STDIN_FIXTURE,
                        'execution_flags': '-I -S -X utf8', 'security': 'reviewed educational snippets, restrictive AST preflight; subprocess is not an OS security sandbox'},
        'evaluation_method': {'scoring_mode': arguments.scoring, 'source_sha256_before_run': method_hashes,
                              'unchanged_during_run': all(hashlib.sha256((evaluation / name).read_bytes()).hexdigest() == expected_hash for name, expected_hash in method_hashes.items())},
        'baseline': {'manifest': manifest, 'unchanged': not changed_after, 'changed_files': changed_after},
        'application': {'project': str(application), 'source_sha256_before_run': application_hashes,
                        'unchanged_during_run': application_unchanged},
        'metrics': aggregate(results),
        'by_difficulty': {difficulty: aggregate([r for r in results if r['difficulty'] == difficulty]) for difficulty in dict.fromkeys(r['difficulty'] for r in results)},
        'failure_categories': dict(Counter(category for r in results if not r['pass'] for category in {c['category'] for c in r['failure_classification']})),
        'cases': results,
    }
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'results.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['id', 'title', 'difficulty', 'status', 'exception_expected', 'exception_actual',
                  'static_warning', 'diagnosis_matched', 'diagnosis_total',
                  'failure_reasons', 'failure_classification', 'expected', 'actual', 'runtime']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = {key: result[key] for key in fields if key in result}
            row.update(exception_expected=result['expected'].get('exception_type'),
                       exception_actual=result['actual'].get('pipeline', {}).get('error', {}).get('error_type'),
                       static_warning=result['checks']['static_warning'],
                       diagnosis_matched=sum(c['matched'] for c in result['checks']['combined_diagnosis']),
                       diagnosis_total=len(result['checks']['combined_diagnosis']))
            for key in ['expected', 'actual', 'runtime', 'failure_reasons', 'failure_classification']:
                row[key] = json.dumps(row[key], ensure_ascii=False)
            writer.writerow(row)
    write_summary(report, output)
    print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
    # FAILは測定対象の結果であり評価器の異常終了ではない。
    return 2 if not application_unchanged else 0


if __name__ == '__main__':
    raise SystemExit(main())
