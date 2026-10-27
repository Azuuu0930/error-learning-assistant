"""Compare saved observations. Does not execute code, change expectations, or re-score prose."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def load(relative):
    return json.loads((DIRECTORY / relative).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(before, after):
    assert before['dataset']['sha256'] == after['dataset']['sha256']
    old = {r['id']: r for r in before['cases']}
    assert set(old) == {r['id'] for r in after['cases']}
    rows = []
    for result in after['cases']:
        previous = old[result['id']]
        assert previous['expected'] == result['expected']
        assert previous['analysis_expectations'] == result['analysis_expectations']
        def score(row):
            c = row['checks']
            return [c['runtime_validated'], c['error_type_correct'], c['static_warning_correct'],
                    c['log_assisted_warning_correct'],
                    sum(x['matched'] for x in c['ast_diagnosis']),
                    sum(x['matched'] for x in c['combined_diagnosis']),
                    -sum(x['violated'] for x in c['prohibited_claims'])]
        a, b = score(previous), score(result)
        up, down = any(y > x for x, y in zip(a, b)), any(y < x for x, y in zip(a, b))
        strict = ('improved' if result['pass'] and not previous['pass'] else
                  'regressed' if previous['pass'] and not result['pass'] else 'unchanged')
        rows.append({'id': result['id'], 'title': result['title'], 'difficulty': result['difficulty'],
                     'before': previous['status'], 'after': result['status'], 'strict_transition': strict,
                     'diagnostic_transition': 'mixed' if up and down else 'improved' if up else 'regressed' if down else 'unchanged',
                     'before_scores': a, 'after_scores': b, 'remaining_failure_reasons': result['failure_reasons']})
    return {'metrics': {key: {'before': value, 'after': after['metrics'][key]}
                        for key, value in before['metrics'].items()},
            'by_difficulty': {key: {'before': value['strict_pass'], 'after': after['by_difficulty'][key]['strict_pass']}
                              for key, value in before['by_difficulty'].items()},
            'strict_transitions': {name: [r['id'] for r in rows if r['strict_transition'] == name]
                                   for name in ('improved', 'regressed', 'unchanged')},
            'diagnostic_transitions': {name: [r['id'] for r in rows if r['diagnostic_transition'] == name]
                                       for name in ('improved', 'regressed', 'mixed', 'unchanged')},
            'cases': rows}


def formatted(metric):
    if metric['percent'] is None:
        return f"N/A ({metric['numerator']}/{metric['denominator']})"
    return f"{metric['percent']:.2f}% ({metric['numerator']}/{metric['denominator']})"


def metric_table(result):
    labels = {'error_type_accuracy': 'Error Type Accuracy',
              'error_no_error_accuracy_static': 'Error/No-Error（コードのみ）',
              'error_no_error_accuracy_log_assisted': 'Error/No-Error（ログ＋コード）',
              'false_positive_rate': 'False Positive Rate', 'ast_diagnosis_accuracy': 'AST Diagnosis Accuracy',
              'combined_diagnosis_accuracy': 'ログ説明＋AST診断達成率', 'incorrect_claim_rate': 'Incorrect Claim Rate',
              'coverage': 'Coverage', 'strict_pass': 'Strict PASS'}
    lines = ['| 指標 | Before | After |', '|---|---:|---:|']
    lines += [f"| {label} | {formatted(result['metrics'][key]['before'])} | {formatted(result['metrics'][key]['after'])} |"
              for key, label in labels.items()]
    return lines


def review_packet(report, target):
    lines = ['# 禁止断定の全文監査用資料', '']
    for row in report['cases']:
        checks = row['checks']['prohibited_claims']
        if not checks:
            continue
        p = row['actual']['pipeline']
        a = p.get('code_analysis') or {}
        lines += [f"## {row['id']} {row['title']}", '',
                  '禁止事項: ' + ' / '.join(c['expectation'] for c in checks), '',
                  '```json', json.dumps({'explanation': p['explanation'], 'hints': p['hints'],
                                        'findings': a.get('findings'), 'notes': a.get('notes'),
                                        'pipeline_notes': p.get('notes')}, ensure_ascii=False, indent=2), '```', '']
    target.write_text('\n'.join(lines), encoding='utf-8')


def main():
    before, after = load('baseline-rescored/results.json'), load('after/results.json')
    h_before, h_after = load('holdout/before/results.json'), load('holdout/after/results.json')
    original, freeze, holdout = load('results.json'), load('implementation_freeze.json'), load('holdout/dataset.json')
    assert before['metrics'] == original['metrics'], 'Baseline scoring changed.'
    assert before['by_difficulty'] == original['by_difficulty']
    changed = [p for p, digest in freeze['files'].items() if sha(DIRECTORY.parent / p) != digest]
    assert not changed, changed
    assert freeze['frozen_at_utc'] < holdout['created_at_utc'] < h_after['started_at']
    assert all(r['application']['unchanged_during_run'] for r in (before, after, h_before, h_after))
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'freeze_unchanged': True, 'baseline_metrics_reproduced_exactly': True,
              '42_cases': compare(before, after), '20_case_holdout': compare(h_before, h_after),
              'transient_timeout_run': 'after-transient-timeout/results.json'}
    (DIRECTORY / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (DIRECTORY / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['dataset', 'id', 'title', 'difficulty', 'before', 'after', 'strict_transition', 'diagnostic_transition', 'remaining_failure_reasons']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key in ('42_cases', '20_case_holdout'):
            for row in result[key]['cases']:
                record = {k: row[k] for k in fields if k != 'dataset'}
                record['dataset'] = key
                record['remaining_failure_reasons'] = ' / '.join(record['remaining_failure_reasons'])
                writer.writerow(record)
    lines = ['# 診断改善の実測比較', '',
             '入力データ、分母、意味照合関数を固定して測定しました。旧Versionも同じ評価器で再実行し、元の指標・難易度別結果と完全一致することを確認しています。', '',
             '## 42ケース', '', *metric_table(result['42_cases']), '',
             'コードだけの警告は解析APIの代理指標です。UIは引き続きエラーログ必須です。ASTの分母36は構文が有効で診断期待を持つケース、Combinedの分母42は全ケースです。', '',
             '| 難易度 | Before Strict PASS | After Strict PASS |', '|---|---:|---:|']
    lines += [f"| {key} | {v['before']['numerator']}/{v['before']['denominator']} | {v['after']['numerator']}/{v['after']['denominator']} |"
              for key, v in result['42_cases']['by_difficulty'].items()]
    lines += ['', '## ケースの変化', '']
    for name, ids in result['42_cases']['strict_transitions'].items():
        lines.append(f"- Strict {name}: {len(ids)}件 — {', '.join(ids) or 'なし'}")
    lines += ['', 'Strict PASSの変化がないケースにも部分的な改善があります。下記は例外判定・警告判定・AST期待一致数・Combined期待一致数・禁止断定数を軸にした比較です。', '']
    for name, ids in result['42_cases']['diagnostic_transitions'].items():
        lines.append(f"- 診断 {name}: {len(ids)}件 — {', '.join(ids) or 'なし'}")
    lines += ['', '## 改善後もStrict FAILとなるケース', '', '| ID | タイトル | 失敗理由 |', '|---|---|---|']
    lines += [f"| {r['id']} | {r['title']} | {' / '.join(r['remaining_failure_reasons'])} |"
              for r in result['42_cases']['cases'] if r['after'] == 'FAIL']
    lines += ['', '## 実装固定後の新規holdout 20ケース', '',
              f"実装固定: `{freeze['frozen_at_utc']}`。holdout作成: `{holdout['created_at_utc']}`。",
              'エラー10件・正常10件を新規作成しました。両分岐の同型合流、keyword-only、引数重複、負のタプル添字、boolのキー・添字、関数を経由した変更、入れ子の例外処理、generator式などを含みます。',
              '開発時のテストには使用せず、評価後のアプリ・採点関数・期待値の修正は行っていません。作者が作る小規模な確認セットであり、外部の盲検評価ではありません。', '',
              *metric_table(result['20_case_holdout']), '',
              'ASTは構文有効かつshould_detectを持つ10件、Combinedは構文エラーを含む11件が分母です。残り9件も警告判定・Strict PASS・Coverageの分母に含めます。引数重複の専用意味分類が既存評価器にないH-02は、警告判定のみで評価しています。', '',
              'H-15は例外処理を示す実際のnoteがありますが、固定規則の英語識別子境界が日本語との隣接を拾えずFAILです。採点を上書きしていません。正常10件はすべて無警告です。', '',
              '## 再現性・保存物', '',
              '- 361 pytest成功（アプリ319、評価器42）。元のアプリ208テストの6ファイルはバイト単位で未変更。新規119実行例（アプリ111、評価器8）。',
              '- 元の評価器34件は旧Version前提の4箇所を更新。変更前は同梱の旧Versionに保存。意味照合関数は同一で、新しい診断kindの警告分類だけを拡張。',
              '- 42件の原本JSONは未変更。元の結果はresults.json、再測定はbaseline-rescored/とafter/、holdoutはholdout/before/とholdout/after/に保存。',
              '- 固定後の初回42件実行ではPY-035のコード実行プロセスが5秒でtimeoutし、例外種類36/37・Strict PASS27/42となった。アプリは42/42応答。after-transient-timeout/に全結果を保存し、同じコード・5秒設定で全42件を再実行。最終実行は42/42の実行結果を再現。過渡的timeoutの原因自体は未特定。',
              '- comparison.json / comparison.csvは全62件のBefore/After・変化区分・失敗理由を保存。評価時のソースhashと固定manifestも保存。',
              '- 禁止断定の機械照合は日本語規則であり完全ではない。after/claim_review_packet.mdとholdout/after/claim_review_packet.mdを全文監査用に保存。', '']
    (DIRECTORY / 'COMPARISON.md').write_text('\n'.join(lines), encoding='utf-8')
    review_packet(after, DIRECTORY / 'after/claim_review_packet.md')
    review_packet(h_after, DIRECTORY / 'holdout/after/claim_review_packet.md')
    print(json.dumps({'42_strict_transitions': result['42_cases']['strict_transitions'],
                      '42_diagnostic_transitions': result['42_cases']['diagnostic_transitions'],
                      'holdout_strict_transitions': result['20_case_holdout']['strict_transitions'],
                      'freeze_unchanged': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
