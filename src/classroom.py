"""匿名相談カードの許可リスト、検証、集計。入力コードやログ本文を扱わない。"""
import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from src.explanations import CATEGORIES, CATEGORY_LABELS

MAX_CARD_BYTES = 16 * 1024
MAX_FILES = 100
MAX_BATCH_BYTES = 1024 * 1024
APP_RELEASE = "2026.10-classroom-1"
LANGUAGES = {"python": "Python", "c": "C", "cpp": "C++"}
ENVIRONMENTS = {"unknown": "不明", "python": "Pythonの実行環境", "notebook": "ノートブック",
                "gcc": "GCC", "clang": "Clang", "msvc": "MSVC", "other": "その他"}
LEARNING_STATUSES = {"unanswered": "未回答", "stuck": "まだ困っている",
                     "next_step": "次に試すことが分かった", "resolved": "解決した（自己申告）"}
PHASES = {"compile": "コンパイル・構文確認", "link": "リンク", "runtime": "実行時", "unknown": "不明"}
CONCEPTS = {"syntax": "文法・字下げ", "names": "変数名・宣言", "scope": "変数の有効範囲",
            "types": "型", "values": "値", "collections": "配列・コレクション", "attributes": "属性・メソッド",
            "imports": "読み込み", "files": "ファイル", "arithmetic": "計算", "functions": "関数・再帰",
            "loops": "繰り返し", "conditions": "条件", "encoding": "文字コード", "build": "ビルド",
            "memory": "メモリアクセス", "runtime": "実行時の操作"}
_CATEGORY_CONCEPTS = {"syntax": ["syntax"], "indentation": ["syntax"], "variable": ["names"],
                      "type": ["types"], "value": ["values"], "index": ["collections"],
                      "key": ["collections"], "attribute": ["attributes"], "module": ["imports"],
                      "import": ["imports"], "file": ["files"], "arithmetic": ["arithmetic"],
                      "recursion": ["functions"], "iteration": ["loops"], "assertion": ["conditions"],
                      "encoding": ["encoding"], "compile": ["build"], "linker": ["build"],
                      "runtime": ["runtime"], "unknown": []}
_C_ERRORS = {"CompilationError", "LinkerError", "SegmentationFault"}
_KEYS = {"schema_version", "card_id", "app_release", "language", "environment", "error_type",
         "diagnostic_code", "category", "phase", "concept_candidates", "analysis_status",
         "hint_step", "fix_viewed", "learning_status"}


def _facts(language, name, category):
    if name == "unknown":
        return "unknown", []
    phase = ("compile" if name in {"SyntaxError", "IndentationError", "IncompleteInputError", "CompilationError"}
             else "link" if name == "LinkerError" else "runtime")
    concepts = (["names", "scope"] if name == "UnboundLocalError" else
                ["memory"] if name == "SegmentationFault" else list(_CATEGORY_CONCEPTS[category]))
    return phase, concepts


def _validate(value):
    # Unknown keys are rejected, not silently dropped: no free-text metadata.
    if type(value) is not dict or set(value) != _KEYS:
        raise ValueError("相談カードの項目が正しくありません。")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["app_release"] != APP_RELEASE:
        raise ValueError("この版の相談カードには対応していません。")
    try:
        ident = UUID(value["card_id"]) if type(value["card_id"]) is str else None
        if ident is None or ident.version != 4 or str(ident) != value["card_id"]:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("カードIDが正しくありません。") from None
    for key, allowed in (("language", LANGUAGES), ("environment", ENVIRONMENTS),
                         ("category", CATEGORY_LABELS), ("phase", PHASES),
                         ("learning_status", LEARNING_STATUSES)):
        if type(value[key]) is not str or value[key] not in allowed:
            raise ValueError("相談カードに対応していない選択値があります。")
    language, name, category = value["language"], value["error_type"], value["category"]
    allowed_names = set(CATEGORIES) if language == "python" else _C_ERRORS
    if type(name) is not str or name not in allowed_names | {"unknown"}:
        raise ValueError("エラーの種類が正しくありません。")
    if name == "unknown":
        valid_categories = {"unknown"}
    elif language == "python":
        valid_categories = {CATEGORIES[name]}
    else:
        valid_categories = ({"syntax", "variable", "type", "module", "compile"} if name == "CompilationError"
                            else {"linker"} if name == "LinkerError" else {"runtime"})
    phase, concepts = _facts(language, name, category)
    if category not in valid_categories or value["phase"] != phase or type(value["concept_candidates"]) is not list or value["concept_candidates"] != concepts:
        raise ValueError("言語・診断・学習概念の対応が一致しません。")
    code = value["diagnostic_code"]
    if code is not None:
        pattern = r"C[0-9]{4}" if name == "CompilationError" else r"LNK[0-9]{4}" if name == "LinkerError" else None
        if language == "python" or type(code) is not str or not pattern or not re.fullmatch(pattern, code):
            raise ValueError("診断コードの対応が正しくありません。")
        # Known MSVC codes have a stable category; unknown codes retain their generic classification.
        from src.c_family import MSVC_CATEGORIES
        if code in MSVC_CATEGORIES and category != MSVC_CATEGORIES[code][1]:
            raise ValueError("診断コードと分類が一致しません。")
    if type(value["analysis_status"]) is not str or value["analysis_status"] not in {"complete", "partial", "unrecognized"}:
        raise ValueError("解析状況が正しくありません。")
    if name != "unknown" and value["analysis_status"] == "unrecognized":
        raise ValueError("診断と解析状況が一致しません。")
    if type(value["hint_step"]) is not int or not 0 <= value["hint_step"] <= 3:
        raise ValueError("ヒント段階が正しくありません。")
    if value["fix_viewed"] is not None and type(value["fix_viewed"]) is not bool:
        raise ValueError("修正例の閲覧情報が正しくありません。")
    if value["fix_viewed"] is True and value["hint_step"] != 3:
        raise ValueError("ヒント段階と修正例の閲覧情報が一致しません。")
    if value["environment"] in {"gcc", "clang", "msvc"} and language == "python" or value["environment"] == "python" and language != "python":
        raise ValueError("言語と実行環境の選択が一致しません。")
    return value


def build_card(result, *, card_id, environment="unknown", learning_status="unanswered", hint_step=0, fix_viewed=None):
    error = result.error
    language = error.language
    name = (error.error_type or "").rsplit(".", 1)[-1]
    allowed = set(CATEGORIES) if language == "python" else _C_ERRORS
    if name not in allowed:
        name, category = "unknown", "unknown"
    else:
        category = error.category
    phase, concepts = _facts(language, name, category)
    value = dict(schema_version=1, card_id=card_id, app_release=APP_RELEASE, language=language,
                 environment=environment, error_type=name, diagnostic_code=getattr(error, "diagnostic_code", None),
                 category=category, phase=phase, concept_candidates=concepts, analysis_status=error.status,
                 hint_step=hint_step, fix_viewed=fix_viewed, learning_status=learning_status)
    return _validate(value)


def encode_card(card):
    return json.dumps(_validate(card), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSONの項目が重複しています。")
        result[key] = value
    return result


def decode_card(data: bytes):
    if type(data) is not bytes or len(data) > MAX_CARD_BYTES:
        raise ValueError("カードは1ファイル16KiB以内のJSONにしてください。")
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("相談カードのJSONを読み取れませんでした。") from None
    return _validate(value)


@dataclass(frozen=True)
class CardBatch:
    cards: tuple[dict, ...]
    invalid: int = 0
    duplicates: int = 0
    conflicts: int = 0
    errors: tuple[str, ...] = ()


def load_cards(payloads):
    if len(payloads) > MAX_FILES or sum(len(p) for p in payloads if type(p) is bytes) > MAX_BATCH_BYTES:
        raise ValueError("一度に読めるのは100ファイル、合計1MiBまでです。")
    groups, errors = {}, []
    for index, data in enumerate(payloads, 1):
        try:
            value = decode_card(data)
        except ValueError as exc:
            errors.append(f"{index}番目のカード：{exc}")
            continue
        groups.setdefault(value["card_id"], []).append(value)
    cards, duplicates, conflicts = [], 0, 0
    for ident in sorted(groups):
        values = groups[ident]
        distinct = {json.dumps(v, sort_keys=True, ensure_ascii=False) for v in values}
        if len(distinct) > 1:
            conflicts += 1
        else:
            cards.append(values[0])
            duplicates += len(values) - 1
    return CardBatch(tuple(cards), len(errors), duplicates, conflicts, tuple(errors))


def summarize(cards, *, language="all", phase="all"):
    if language not in {"all", *LANGUAGES} or phase not in {"all", *PHASES}:
        raise ValueError("絞り込み条件が正しくありません。")
    values = [_validate(v) for v in cards]
    values = [v for v in values if (language == "all" or v["language"] == language)
              and (phase == "all" or v["phase"] == phase)]
    count = lambda key: dict(Counter(v[key] for v in values))
    return dict(total=len(values), stuck=sum(v["learning_status"] == "stuck" for v in values),
                hint3=sum(v["hint_step"] == 3 for v in values),
                unanswered=sum(v["learning_status"] == "unanswered" for v in values),
                fix_unmeasured=sum(v["fix_viewed"] is None for v in values),
                by_language=count("language"), by_phase=count("phase"), by_status=count("learning_status"),
                by_error=dict(Counter(v["error_type"] + (f" / {v['diagnostic_code']}" if v["diagnostic_code"] else "") for v in values)),
                by_concept=dict(Counter(c for v in values for c in v["concept_candidates"])))


def summary_csv(summary):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["項目", "区分", "相談件数"])
    for title, key, labels in (("言語", "by_language", LANGUAGES), ("発生段階", "by_phase", PHASES),
                                ("状態（自己申告）", "by_status", LEARNING_STATUSES),
                                ("学習概念の候補", "by_concept", CONCEPTS), ("エラーの種類・診断コード", "by_error", {})):
        for value, count in sorted(summary[key].items()):
            writer.writerow([title, labels.get(value, value), count])
    return out.getvalue().encode("utf-8-sig")


def card_preview(card):
    v = _validate(card)
    viewed = "未計測" if v["fix_viewed"] is None else "見た" if v["fix_viewed"] else "見ていない"
    return {"カードID": v["card_id"], "言語": LANGUAGES[v["language"]], "実行環境（本人の選択）": ENVIRONMENTS[v["environment"]],
            "エラーの種類": v["error_type"], "診断コード": v["diagnostic_code"] or "なし",
            "アプリの分類": CATEGORY_LABELS[v["category"]], "発生段階（ログから推定）": PHASES[v["phase"]],
            "学習概念の候補": [CONCEPTS[c] for c in v["concept_candidates"]],
            "解析状況": {"complete": "必要な情報を取得", "partial": "一部の情報を取得", "unrecognized": "未認識"}[v["analysis_status"]],
            "見たヒント": v["hint_step"], "修正例の閲覧": viewed,
            "状態（自己申告）": LEARNING_STATUSES[v["learning_status"]]}
