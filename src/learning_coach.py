"""Allowlisted learning context and locally authored questions; never execute code."""
from dataclasses import dataclass

from src.explanations import CATEGORIES
from src.models import AnalysisResult


GOALS = {"locate": "エラーの場所を読み直したい", "understand": "注目する名前・操作を整理したい",
         "check": "次に何を確認するか考えたい"}

# Each question is an invitation to verify, not an additional diagnosis.
QUESTIONS = {
    "undefined_name": "この名前に値を与える処理は、同じスコープのどこにありますか？",
    "similar_name": "似た名前の候補と使っている名前は、どの文字が違いますか？",
    "use_before_definition": "名前に値を与える行と、その名前を読む行は、どちらが先ですか？",
    "possibly_unbound": "その行までに値が代入されない経路があるか、分岐やループをたどれますか？",
    "import_match": "ログの読み込み名とimport文を比べ、同じ実行環境で使えるかを何で確かめますか？",
    "attribute_access": "ドットの左側の値に、右側の機能があるかを何で確かめますか？",
    "missing_attribute": "その値が持つ属性と、呼び出そうとした属性をどこで比べられますか？",
    "index_out_of_range": "要素数と位置番号を、負の位置も含めて比べると何が分かりますか？",
    "invalid_index_type": "角括弧の位置指定に使っている値は、どんな型ですか？",
    "incompatible_operation": "演算子の左側と右側の型を、それぞれどう確認できますか？",
    "call_arguments": "関数の定義と呼び出しで、引数の数・名前・初期値は対応していますか？",
    "unhashable_key": "辞書のキーや集合の要素に使う値の型について、何を確認しますか？",
    "missing_key": "辞書にあるキーと取り出そうとしたキーを、どこで比べられますか？",
    "zero_division": "割る側の値がその行までにどう決まるか、一つずつたどれますか？",
    "invalid_conversion": "変換元の値と変換先の型の条件を、どう確かめますか？",
    "assertion_failure": "assertの条件を小さく分けたとき、それぞれ何を確認していますか？",
    "empty_iterator": "次の要素を取り出す前に、空や取り出し済みかどうかをどう確認しますか？",
    "iteration_mutation": "反復を続けている間に、辞書や集合の要素数を変える処理はありますか？",
}
KINDS = {
    "NameError": {"undefined_name", "similar_name", "use_before_definition", "possibly_unbound"},
    "UnboundLocalError": {"undefined_name", "use_before_definition", "possibly_unbound"},
    "TypeError": {"invalid_index_type", "incompatible_operation", "call_arguments", "unhashable_key"},
    "IndexError": {"index_out_of_range"}, "KeyError": {"missing_key"},
    "AttributeError": {"missing_attribute", "attribute_access"},
    "ImportError": {"import_match"}, "ModuleNotFoundError": {"import_match"},
    "ZeroDivisionError": {"zero_division"}, "ValueError": {"invalid_conversion"},
    "AssertionError": {"assertion_failure"}, "StopIteration": {"empty_iterator"},
    "RuntimeError": {"iteration_mutation"},
}


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: str
    confidence: str
    line: int | None


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    basis_id: str
    confidence: str


@dataclass(frozen=True)
class CoachContext:
    error_type: str
    line: int | None
    goal: str
    evidence: tuple[Evidence, ...]
    candidates: tuple[Question, ...]

    def to_dict(self) -> dict:
        # Explicit DTO: never export any of the application's dataclasses.
        return {"error_type": self.error_type, "line": self.line, "goal": self.goal,
                "evidence": [{"id": e.id, "kind": e.kind, "confidence": e.confidence, "line": e.line}
                             for e in self.evidence],
                "candidates": [{"id": q.id, "text": q.text, "basis_id": q.basis_id}
                               for q in self.candidates]}


def _line(value) -> int | None:
    return value if type(value) is int and 1 <= value <= 1_000_000 else None


def build_context(result: AnalysisResult, goal: str) -> CoachContext:
    if goal not in GOALS:
        raise ValueError("Unknown learning goal")
    name = (result.error.error_type or "").rsplit(".", 1)[-1]
    name = name if name in CATEGORIES else "unknown"
    line = _line(result.error.line)
    evidence = [Evidence("log", "reported_error", "reported", line)]
    general = [Question("locate.log", "エラー履歴の最後に記録された行番号と、貼り付けたコードの行は対応していますか？", "log", "reported"),
               Question("understand.log", "最後の例外行から、失敗した操作を自分の言葉で説明できますか？", "log", "reported"),
               Question("check.log", "表示済みの確認ポイントから、一つだけ確かめるとしたら何を選びますか？", "log", "reported")]
    specific = []
    if result.code_analysis and result.code_analysis.status == "parsed":
        for index, finding in enumerate(result.code_analysis.findings):
            if len(evidence) >= 9:
                break
            if (finding.kind not in KINDS.get(name, set()) or _line(finding.line) is None
                    or finding.confidence not in {"high", "medium", "low"}
                    or (line is not None and finding.line != line)):
                continue
            if (name in {"NameError", "UnboundLocalError", "AttributeError"}
                    and result.error.target and finding.target != result.error.target):
                continue
            ident = f"finding_{index}"
            evidence.append(Evidence(ident, finding.kind, finding.confidence, finding.line))
            specific.append(Question(f"{finding.kind}.{ident}", QUESTIONS[finding.kind], ident, finding.confidence))
    preferred = next(q for q in general if q.id.startswith(goal + "."))
    candidates = specific + [preferred] if goal == "check" else [preferred] + specific
    candidates += [q for q in general if q != preferred]
    return CoachContext(name, line, goal, tuple(evidence), tuple(candidates))


def validate_choice(context: CoachContext, data: dict) -> Question:
    if type(data) is not dict or set(data) != {"question_id", "basis_ids"}:
        raise ValueError("Invalid choice shape")
    candidate = next((q for q in context.candidates if q.id == data["question_id"]), None)
    basis = data["basis_ids"]
    if candidate is None or type(basis) is not list or basis != [candidate.basis_id]:
        raise ValueError("Invalid question or evidence")
    return candidate


def standard_question(context: CoachContext) -> Question:
    return context.candidates[0]
