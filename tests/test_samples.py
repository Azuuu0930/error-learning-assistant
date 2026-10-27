"""固定の学習用サンプルを検証する。アプリが入力コードを実行する機能ではない。"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.analyzer import analyze_error
from src.parser import SUPPORTED_ERRORS


SAMPLES = json.loads((Path(__file__).resolve().parents[1] / "examples" / "sample_errors.json").read_text(encoding="utf-8"))


def test_sample_catalog_covers_all_supported_errors():
    assert len(SAMPLES) >= 10
    assert {sample["error_type"] for sample in SAMPLES} == set(SUPPORTED_ERRORS)
    assert len({sample["id"] for sample in SAMPLES}) == len(SAMPLES)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
def test_sample_log_and_source_are_consistent(sample):
    assert {"code", "error_log", "error_type", "cause", "checkpoints", "fix_example"} <= sample.keys()
    result = analyze_error(sample["error_log"], sample["code"])
    assert result.error.error_type == sample["error_type"]
    assert result.error.message
    assert result.error.file == f'{sample["id"]}.py'
    assert result.error.status == "complete"
    assert any(line.is_error for line in result.code_context)
    assert sample["cause"] and sample["checkpoints"] and sample["fix_example"]


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
def test_trusted_sample_correction_runs(sample, tmp_path):
    script = tmp_path / "corrected.py"
    script.write_text(sample["fix_example"], encoding="utf-8")
    completed = subprocess.run([sys.executable, script.name], cwd=tmp_path,
                               capture_output=True, encoding="utf-8",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=15)
    assert completed.returncode == 0, completed.stderr
