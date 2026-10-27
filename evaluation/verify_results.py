"""Read-only consistency checks for the saved baseline, frozen implementation and measurements."""
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from evaluation.evaluate import aggregate, baseline_changed, load_dataset


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evaluation = PROJECT / 'evaluation'
    baseline = PROJECT.parent / 'error-learning-assistant-baseline'
    freeze = load(evaluation / 'implementation_freeze.json')
    assert all(sha(PROJECT / p) == h for p, h in freeze['files'].items())
    assert not baseline_changed(load(evaluation / 'baseline_manifest.json'), baseline)
    for name, h in freeze['original_app_test_files_unchanged'].items():
        assert sha(PROJECT / name) == sha(baseline / name) == h
    preserved_core = ['app.py', 'src/parser.py', 'src/models.py', 'src/view.py', 'requirements.txt']
    assert all((PROJECT / p).read_bytes() == (baseline / p).read_bytes() for p in preserved_core)
    def functions(path):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}
    assert functions(PROJECT / 'evaluation/scoring.py') == functions(baseline / 'evaluation/scoring.py')
    assert functions(PROJECT / 'evaluation/evaluate.py')['aggregate'] == functions(baseline / 'evaluation/evaluate.py')['aggregate']
    dataset = evaluation / 'python_error_evaluation_dataset.json'
    assert sha(dataset) == load(evaluation / 'baseline_manifest.json')['dataset_sha256']
    assert load_dataset(dataset)[1] == load_dataset(evaluation / 'python_error_evaluation_dataset.jsonl')[1]
    reports = {}
    for name in ['results.json', 'baseline-rescored/results.json', 'after/results.json',
                 'after-transient-timeout/results.json', 'holdout/before/results.json', 'holdout/after/results.json']:
        path = evaluation / name
        data = load(path)
        assert aggregate(data['cases']) == data['metrics']
        assert len(data['cases']) == len({r['id'] for r in data['cases']})
        with path.with_suffix('.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        assert [r['id'] for r in rows] == [r['id'] for r in data['cases']]
        assert [r['status'] for r in rows] == [r['status'] for r in data['cases']]
        if 'application' in data:
            assert data['application']['unchanged_during_run']
        if name.startswith(('after/', 'holdout/after/')):
            assert all(sha(PROJECT / p) == h for p, h in data['application']['source_sha256_before_run'].items())
        reports[name] = {'cases': len(rows), 'runtime_validated': data['metrics']['runtime_validated'],
                         'strict_pass': data['metrics']['strict_pass'], 'coverage': data['metrics']['coverage']}
    original = load(evaluation / 'results.json')
    rescored = load(evaluation / 'baseline-rescored/results.json')
    assert original['metrics'] == rescored['metrics']
    assert original['by_difficulty'] == rescored['by_difficulty']
    h_path = evaluation / 'holdout/dataset.json'
    holdout = load(h_path)
    assert freeze['frozen_at_utc'] < holdout['created_at_utc']
    for name in ('before', 'after'):
        data = load(evaluation / f'holdout/{name}/results.json')
        assert data['dataset']['sha256'] == sha(h_path)
        assert holdout['created_at_utc'] < data['started_at']
    for path in [PROJECT / 'app.py', *(PROJECT / 'src').glob('*.py')]:
        assert not re.search(r'\b(?:PY-\d{3}|H-\d{2})\b|evaluation_dataset', path.read_text(encoding='utf-8'))
    comparison = load(evaluation / 'comparison.json')
    assert not comparison['42_cases']['strict_transitions']['regressed']
    assert not comparison['42_cases']['diagnostic_transitions']['regressed']
    assert not comparison['20_case_holdout']['strict_transitions']['regressed']
    verification = {'verified_at_utc': datetime.now(timezone.utc).isoformat(),
                    'frozen_files_unchanged': len(freeze['files']),
                    'original_app_test_files_unchanged': len(freeze['original_app_test_files_unchanged']),
                    'preserved_core_files': preserved_core, 'semantic_scoring_functions_identical': True,
                    'aggregate_function_identical': True, 'baseline_metrics_reproduced_exactly': True,
                    'dataset_json_jsonl_cases_identical': True, 'dataset_sha256': sha(dataset),
                    'holdout_created_after_freeze': True, 'holdout_sha256': sha(h_path),
                    'holdout_expectations_match_before_after': True,
                    'reports_metrics_recomputed_and_csv_consistent': reports,
                    'pytest_actual_run': freeze['pytest'],
                    'limitations': 'Hash and result consistency checks; not a new accuracy estimate or a proof of no dataset-specific behavior.'}
    (evaluation / 'verification-v2.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
