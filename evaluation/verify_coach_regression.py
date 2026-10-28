"""Compare deterministic output to stored reports; no snippet execution or AI.

Run from any directory: python evaluation/verify_coach_regression.py
The saved stderr is an input fixture, not a newly measured runtime outcome.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from src.analyzer import analyze_error
from src.code_analysis import analyze_code


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    pairs = (("42-case", "evaluation/python_error_evaluation_dataset.json", "v3-structured"),
             ("known-holdout", "evaluation/holdout/dataset.json", "old-holdout-v3"),
             ("normal-corpus", "evaluation/v3/normal-corpus.json", "normal-v3"))
    reports = []
    for label, dataset, run in pairs:
        data = load(PROJECT / dataset)
        cases = data if isinstance(data, list) else data["cases"]
        saved = load(PROJECT / "evaluation/v3" / run / "results.json")
        sources = {case["id"]: case["code"] for case in cases}
        differences = []
        for row in saved["cases"]:
            code = sources[row["id"]]
            current = {"status": "returned", "pipeline": asdict(analyze_error(row["runtime"]["stderr"], code)),
                       "static": asdict(analyze_code(code))}
            current = json.loads(json.dumps(current, ensure_ascii=False))
            if current != row["actual"]:
                differences.append(row["id"])
        reports.append({"name": label, "cases": len(cases), "identical": len(cases) - len(differences),
                        "differences": differences})
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "method": "Current analyzer and static outputs compared to saved outputs using saved stderr; no code execution or AI request.",
              "runs": reports,
              "core_sha256": {f"src/{name}": hashlib.sha256((PROJECT / "src" / name).read_bytes()).hexdigest()
                  for name in ("analyzer.py", "parser.py", "code_analysis.py", "literal_analysis.py", "safe_summaries.py", "models.py", "hints.py", "explanations.py")}}
    destination = PROJECT / "evaluation/hackathon"
    destination.mkdir(exist_ok=True)
    (destination / "diagnostic-regression.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(r["differences"] for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
