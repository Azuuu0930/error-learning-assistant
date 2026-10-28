"""解析・説明・表示で共有する小さなデータ構造。"""

from dataclasses import asdict, dataclass, field
from typing import Literal


@dataclass(frozen=True)
class TraceFrame:
    file: str
    line: int
    function: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class ParsedError:
    language: str = "python"
    error_type: str | None = None
    message: str = ""
    file: str | None = None
    line: int | None = None
    target: str | None = None
    category: str = "unknown"
    frames: tuple[TraceFrame, ...] = ()
    status: Literal["complete", "partial", "unrecognized"] = "unrecognized"
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Explanation:
    summary: str
    cause: str
    checkpoints: tuple[str, ...]
    reading_tip: str
    fix_example: str | None = None
    fix_note: str = "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"


@dataclass(frozen=True)
class CodeLine:
    number: int
    text: str
    is_error: bool


@dataclass(frozen=True)
class CodeFinding:
    kind: str
    message: str
    confidence: Literal["high", "medium", "low"]
    line: int
    target: str | None = None
    related_names: tuple[str, ...] = ()
    evidence: str = ""
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CodeFact:
    kind: str
    line: int
    subject: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NameDefinition:
    name: str
    line: int
    scope: str
    kind: str


@dataclass(frozen=True)
class NameUse:
    name: str
    line: int
    scope: str


@dataclass(frozen=True)
class ImportInfo:
    module: str
    imported_name: str | None
    bound_name: str | None
    line: int


@dataclass(frozen=True)
class AttributeAccess:
    expression: str
    attribute: str
    line: int


@dataclass(frozen=True)
class SyntaxDiagnostic:
    """入力コードの構文診断。ログに記録された場所とは別の座標。"""

    error_type: str
    message: str
    line: int | None
    column: int | None
    source_line: str
    explanation: Explanation


@dataclass(frozen=True)
class CodeAnalysis:
    status: Literal["parsed", "unavailable"]
    findings: tuple[CodeFinding, ...] = ()
    definitions: tuple[NameDefinition, ...] = ()
    uses: tuple[NameUse, ...] = ()
    imports: tuple[ImportInfo, ...] = ()
    attributes: tuple[AttributeAccess, ...] = ()
    notes: tuple[str, ...] = ()
    facts: tuple[CodeFact, ...] = ()
    syntax_error: SyntaxDiagnostic | None = None

    @property
    def defined_names(self) -> tuple[str, ...]:
        return tuple(sorted({item.name for item in self.definitions}))

    @property
    def used_names(self) -> tuple[str, ...]:
        return tuple(sorted({item.name for item in self.uses}))


@dataclass(frozen=True)
class AnalysisResult:
    error: ParsedError
    explanation: Explanation
    hints: tuple[str, str, str]
    code_context: tuple[CodeLine, ...] = ()
    notes: tuple[str, ...] = ()
    code_analysis: CodeAnalysis | None = None
