"""Rebuild the v3 comparison from saved runs; never change scores or expectations."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import csv
import hashlib
import json
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from evaluation.compare import compare, metric_table, review_packet
from evaluation.evaluate import aggregate

DIRECTORY = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze = load(DIRECTORY / 'freeze.json')
    assert all(sha(PROJECT / k) == v for k, v in freeze['files'].items()), 'Frozen source changed.'
    v2 = PROJECT.parent / 'error-learning-assistant-v2'
    assert (PROJECT / 'evaluation/scoring.py').read_bytes() == (v2 / 'evaluation/scoring.py').read_bytes()
    for test in (v2 / 'tests').glob('test_*.py'):
        assert test.read_bytes() == (PROJECT / 'tests' / test.name).read_bytes()
    normal = load(DIRECTORY / 'normal-corpus.json')
    assert freeze['frozen_at_utc'] < normal['created_at_utc']
    runs = {}
    for name in ('v2-legacy', 'v3-legacy', 'v2-structured', 'v3-structured',
                 'old-holdout-v2', 'old-holdout-v3', 'normal-v2', 'normal-v3'):
        result = load(DIRECTORY / name / 'results.json')
        assert result['metrics'] == aggregate(result['cases'])
        assert result['application']['unchanged_during_run'] and result['evaluation_method']['unchanged_during_run']
        with (DIRECTORY / name / 'results.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        assert [(r['id'], r['status']) for r in rows] == [(r['id'], r['status']) for r in result['cases']]
        app = PROJECT if name.endswith('v3') or name.startswith('v3-') else v2
        assert all(sha(app / k) == v for k, v in result['application']['source_sha256_before_run'].items())
        if name.startswith('normal-'):
            assert result['dataset']['sha256'] == sha(DIRECTORY / 'normal-corpus.json')
            assert normal['created_at_utc'] < result['started_at']
        runs[name] = result
    previous = load(PROJECT / 'evaluation/after/results.json')
    assert previous['metrics'] == runs['v2-legacy']['metrics'], 'Prior v2 baseline did not reproduce.'
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'legacy_42': compare(runs['v2-legacy'], runs['v3-legacy']),
              'structured_42': compare(runs['v2-structured'], runs['v3-structured']),
              'existing_holdout_20': compare(runs['old-holdout-v2'], runs['old-holdout-v3']),
              'new_normal_30': compare(runs['normal-v2'], runs['normal-v3'])}
    (DIRECTORY / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (DIRECTORY / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['comparison', 'id', 'title', 'difficulty', 'before', 'after', 'strict_transition', 'diagnostic_transition', 'remaining_failure_reasons']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key in ('legacy_42', 'structured_42', 'existing_holdout_20', 'new_normal_30'):
            for row in result[key]['cases']:
                record = {k: row[k] for k in fields if k != 'comparison'}
                record['comparison'] = key
                record['remaining_failure_reasons'] = ' / '.join(record['remaining_failure_reasons'])
                writer.writerow(record)
    lines = ['# V3：診断の根拠と学習体験の改善', '',
             '旧版は前回納品したv2です。元の42件・期待・分母・Strict PASS条件を維持し、従来採点と構造化採点を区別しました。', '',
             '## 構造化採点で同じ42件を比較', '', *metric_table(result['structured_42']), '',
             '構造化採点はアプリのdetails/factsを使います。旧版も同じ新採点器で測定しています。元コードやtracebackの文章を新しい診断として加点せず、対象・型・引数数が一致しない根拠は拒否します。', '',
             '## 従来採点をそのまま再現した場合', '', *metric_table(result['legacy_42']), '',
             '従来のscoring.pyはバイト単位で未変更です。この完全再現モードでは新しいwarning kindも認識しません。',
             '新採点との差は、診断内容の追加に加え、既にある内容を新しい根拠形式で確実に拾える効果と新kindの認識を含みます。新採点の増加分をすべて新しい原因推論の成果とは説明しません。', '',
             '## 難易度別Strict PASS（構造化採点）', '', '| 難易度 | v2 | v3 |', '|---|---:|---:|']
    for name, values in result['structured_42']['by_difficulty'].items():
        lines.append(f"| {name} | {values['before']['numerator']}/{values['before']['denominator']} | {values['after']['numerator']}/{values['after']['denominator']} |")
    lines += ['', '## ケースの変化（構造化採点）', '']
    for key, ids in result['structured_42']['strict_transitions'].items():
        lines.append(f"- Strict {key}: {len(ids)}件 — {', '.join(ids) or 'なし'}")
    for key, ids in result['structured_42']['diagnostic_transitions'].items():
        lines.append(f"- 診断 {key}: {len(ids)}件 — {', '.join(ids) or 'なし'}")
    lines += ['', '## 残るFAIL', '', '| ID | タイトル | 失敗理由 |', '|---|---|---|']
    for row in result['structured_42']['cases']:
        if row['after'] == 'FAIL':
            lines.append(f"| {row['id']} | {row['title']} | {' / '.join(row['remaining_failure_reasons'])} |")
    lines += ['', 'import先・ファイルの実在（3件）は環境依存で断定しません。再帰の非停止・UTF-8復号（2件）はコードのみの警告を未実装です。ログ説明では全診断期待を満たしています。', '',
              '## 既存holdout20件の再確認', '', *metric_table(result['existing_holdout_20']), '',
              'この20件は前回から既知の回帰セットです。今回新たな未知データとしては扱いません。', '',
              '## 実装固定後の新しい正常コード30件', '', *metric_table(result['new_normal_30']), '',
              '公式Pythonチュートリアルから実行可能な形へ改変した10件と、新規作成20件。出典URLと変更内容はnormal-corpus.jsonに各件記録しました。外部の盲検ベンチマークではありません。',
              '全件が正常終了することを同じ分離実行・固定stdin20・5秒timeoutで確認しました。警告有無を測る目的でshould_detectを付けていないため、AST診断とCombined診断は0/0=N/Aです。',
              'N-09（tryの中でinput/intし、成功時だけbreakするwhile True）の後のxに、両版ともpossibly_unboundを出します。ループを抜ける経路と代入の関係を十分に理解できない既存のcontrol-flowの制限です。誤警告1/30を隠さず保存し、固定後の評価をアプリ修正には使っていません。', '',
              '## テスト・レビュー・固定', '',
              '- 496 passed in 20.69s。アプリ422、評価器74。前回361件を維持し、今回135件（診断99、UI4、採点32）を追加。元のアプリテストはバイト単位で未変更。',
              '- 独立レビューの15プローブを通過。異なる型・対象への誤加点を3件のRED→GREENテストで修正。残るP1/P2指摘なし。',
              f"- 実装固定: {freeze['frozen_at_utc']}。正常コード作成: {normal['created_at_utc']}。34個の固定ファイルを照合し、評価後のアプリ・採点変更なし。",
              '- 前回v2のlegacy全指標を今回の評価器で完全再現。全実行のJSON/CSV・console.log・hashを保存。クラッシュ・timeout・実行拒否は分母から除外しない。',
              '- ここでのError/No-ErrorはAPIの警告代理指標。UIは引き続きログ入力必須であり、正常性を証明する機能ではない。', '',
              '## 出典', '',
              '- [Python公式：Data Structures](https://docs.python.org/3.12/tutorial/datastructures.html)',
              '- [Python公式：More Control Flow Tools](https://docs.python.org/3.12/tutorial/controlflow.html)',
              '- [Python公式：Errors and Exceptions](https://docs.python.org/3.12/tutorial/errors.html)', '']
    (DIRECTORY / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    review_packet(runs['v3-structured'], DIRECTORY / 'claim_review_packet.md')
    review_packet(runs['old-holdout-v3'], DIRECTORY / 'old_holdout_claim_review_packet.md')
    verification = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'fixed_file_hashes_match': len(freeze['files']),
                    'prior_v2_metrics_reproduced_exactly': True, 'legacy_scoring_byte_identical': True,
                    'all_saved_metrics_recomputed': True, 'all_json_csv_statuses_match': True,
                    'normal_corpus_created_after_freeze': True, 'normal_corpus_sha256': sha(DIRECTORY / 'normal-corpus.json'),
                    'all_runtime_expectations_reproduced': all(r['metrics']['runtime_validated']['numerator'] == len(r['cases']) for r in runs.values()),
                    'tests': freeze['pytest'], 'normal_false_positives': {v: runs[f'normal-{v}']['metrics']['false_positive_rate'] for v in ('v2', 'v3')}}
    (DIRECTORY / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'verification': verification,
                      'transitions': result['structured_42']['strict_transitions'],
                      'diagnostic_transitions': result['structured_42']['diagnostic_transitions']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
