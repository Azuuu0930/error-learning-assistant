# Prohibited claim review packet

## PY-001 変数名のタイプミス

Prohibited: username が確実な正解

{
  "explanation": {
    "summary": "Pythonが「user_name」という名前を使おうとしましたが、その場所で見つけられませんでした。",
    "cause": "変数が使用前に作られていない、スペルが違う、または使える範囲の外にある可能性があります。",
    "checkpoints": [
      "その名前を使う前に値を代入しているか確認してください。",
      "定義した名前と、大文字・小文字を含めてスペルが一致するか確認してください。",
      "関数の中で作った変数を、関数の外から使っていないか確認してください。"
    ],
    "reading_tip": "最後の行の name の後ろが、Pythonが見つけられなかった名前です。",
    "fix_example": "user_name = \"Taro\"\nprint(user_name)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "エラー行で使っている変数名を確認してください。",
    "似た名前の変数がコード内にないか探し、つづりを比べてみてください。",
    "「user_name」と「username」を比較してください。タイプミスの候補ですが、意図した名前は自分で確認しましょう。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [
      {
        "kind": "undefined_name",
        "message": "「user_name」を使っていますが、このスコープから参照できる定義が貼り付けたコードには見つかりません。未定義名の候補です。",
        "confidence": "medium",
        "line": 2,
        "target": "user_name",
        "related_names": [],
        "evidence": "user_name"
      },
      {
        "kind": "similar_name",
        "message": "「user_name」に似た定義名「username」があります。変数名のタイプミスの可能性があります。",
        "confidence": "medium",
        "line": 2,
        "target": "user_name",
        "related_names": [
          "username"
        ],
        "evidence": "user_name"
      }
    ],
    "definitions": [
      {
        "name": "username",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 2,
        "scope": "top@0"
      },
      {
        "name": "user_name",
        "line": 2,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-008 存在しないメソッド

Prohibited: append に直せば必ず正しい

{
  "explanation": {
    "summary": "そのデータには、「apend」という属性・メソッドがありませんでした。",
    "cause": "データの種類に合わない機能を呼んでいる、スペルが違う、または値が None の可能性があります。",
    "checkpoints": [
      "ドットの左側にある値を type() で確認してください。",
      "その種類のデータに、指定した機能があるか確認してください。",
      "名前のスペルや、関数が None を返していないか確認してください。"
    ],
    "reading_tip": "has no attribute の後ろに、存在しない機能の名前が書かれています。",
    "fix_example": "names = [\"Taro\"]\nnames.append(\"Hanako\")\nprint(names)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "エラー行のドットの前後を確認してください。",
    "ドットの左側の値が、右側の機能を持っているか調べてみてください。",
    "2行目の「text.apend」に注目してください。属性があるかは実行時の型や値の確認が必要です。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [
      {
        "kind": "attribute_access",
        "message": "2行目の「text.apend」で属性「apend」へアクセスしています。その属性が実際の値にあるかは、型や実行時の値を確認してください。",
        "confidence": "high",
        "line": 2,
        "target": "apend",
        "related_names": [
          "text.apend"
        ],
        "evidence": "text.apend"
      }
    ],
    "definitions": [
      {
        "name": "text",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "text",
        "line": 2,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [
      {
        "expression": "text.apend",
        "attribute": "apend",
        "line": 2
      }
    ],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-011 存在しないファイルを開く

Prohibited: ファイルが必ず存在しない

{
  "explanation": {
    "summary": "開こうとしたファイル、またはその途中のフォルダが見つかりませんでした。",
    "cause": "ファイル名やパスが違う、または実行時の作業フォルダが想定と違う可能性があります。",
    "checkpoints": [
      "ファイル名・拡張子・大文字と小文字を確認してください。",
      "Path.cwd() で現在の作業フォルダを確認してください。相対パスはそこから探します。",
      "ファイルが実際にあるか、必要なフォルダも含めて確認してください。"
    ],
    "reading_tip": "メッセージ末尾のパスが、Pythonが見つけられなかったファイルです。",
    "fix_example": "from pathlib import Path\n\npath = Path(\"data.txt\")\nif path.is_file():\n    print(path.read_text(encoding=\"utf-8\"))\nelse:\n    print(f\"ファイルを確認してください: {path.resolve()}\")",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "<evaluation>/snippet.py の 1 行目付近を確認してください。文法エラーでは直前の行も見てみましょう。",
    "メッセージに出てくる「絶対に存在しないファイル_12345.txt」に注目してください。コードのどこで使っていますか？",
    "ファイル名・拡張子・大文字と小文字を確認してください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "f",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "open",
        "line": 1,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 2,
        "scope": "top@0"
      },
      {
        "name": "f",
        "line": 2,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [
      {
        "expression": "f.read",
        "attribute": "read",
        "line": 2
      }
    ],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-017 代入演算子と比較演算子の混同

Prohibited: 常に == が正解

{
  "explanation": {
    "summary": "Pythonがコードの書き方を読み取れず、実行を始められませんでした。",
    "cause": "コロン・括弧・引用符などの不足や、文法に合わない書き方が考えられます。",
    "checkpoints": [
      "表示された行だけでなく、直前の行も確認してください。",
      "if / for / def などの末尾に : があるか確認してください。",
      "括弧と引用符が閉じているか、ログの ^ が指す位置も確認してください。"
    ],
    "reading_tip": "^ はPythonが文法の問題に気づいた位置です。原因が前の行にあることもあります。",
    "fix_example": "age = 20\nif age >= 18:\n    print(\"成人です\")",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "<evaluation>/snippet.py の 2 行目付近を確認してください。文法エラーでは直前の行も見てみましょう。",
    "最後の行の「SyntaxError」と、その後ろのメッセージを読み、失敗した操作を探してみてください。",
    "表示された行だけでなく、直前の行も確認してください。"
  ],
  "code_analysis": {
    "status": "unavailable",
    "findings": [],
    "definitions": [],
    "uses": [],
    "imports": [],
    "attributes": [],
    "notes": [
      "2行目付近でASTを生成・解析できませんでした（invalid syntax. Maybe you meant '==' or ':=' instead of '='?）。ログ解析の結果とヒントは引き続き表示します。"
    ]
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-019 ローカル変数の参照前代入

Prohibited: 単純なグローバル変数未定義

{
  "explanation": {
    "summary": "「UnboundLocalError」を検出しました。この種類の専用説明はまだありません。",
    "cause": "原因は断定できません。元のメッセージと、発生した操作を照らし合わせてください。",
    "checkpoints": [
      "最後の行のエラー種類とメッセージを確認してください。",
      "表示されたファイル・行番号の操作を確認してください。",
      "独自の例外なら、その例外を送出する箇所や公式資料を確認してください。"
    ],
    "reading_tip": "未知のエラーでも、末尾のメッセージと最後のフレームが調査の出発点になります。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "エラー行で使っている変数名を確認してください。",
    "値を代入する行と使う行は、どちらが先にありますか？",
    "「count」の使用と定義の順序を確認してください。この参照までに値を与えていますか？"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [
      {
        "kind": "use_before_definition",
        "message": "「count」にはこのスコープ内に定義がありますが、4行目の参照までには値を与える処理が見つかりません。使用と定義の順序を確認してください。",
        "confidence": "high",
        "line": 4,
        "target": "count",
        "related_names": [],
        "evidence": "count"
      }
    ],
    "definitions": [
      {
        "name": "count",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "test",
        "line": 3,
        "scope": "top@0",
        "kind": "function"
      },
      {
        "name": "count",
        "line": 5,
        "scope": "test@3",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 4,
        "scope": "test@3"
      },
      {
        "name": "count",
        "line": 4,
        "scope": "test@3"
      },
      {
        "name": "test",
        "line": 7,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-034 自作クラスの存在しない属性

Prohibited: name が age の確実な修正候補

{
  "explanation": {
    "summary": "そのデータには、「age」という属性・メソッドがありませんでした。",
    "cause": "データの種類に合わない機能を呼んでいる、スペルが違う、または値が None の可能性があります。",
    "checkpoints": [
      "ドットの左側にある値を type() で確認してください。",
      "その種類のデータに、指定した機能があるか確認してください。",
      "名前のスペルや、関数が None を返していないか確認してください。"
    ],
    "reading_tip": "has no attribute の後ろに、存在しない機能の名前が書かれています。",
    "fix_example": "names = [\"Taro\"]\nnames.append(\"Hanako\")\nprint(names)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "エラー行のドットの前後を確認してください。",
    "ドットの左側の値が、右側の機能を持っているか調べてみてください。",
    "6行目の「user.age」に注目してください。属性があるかは実行時の型や値の確認が必要です。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [
      {
        "kind": "attribute_access",
        "message": "6行目の「user.age」で属性「age」へアクセスしています。その属性が実際の値にあるかは、型や実行時の値を確認してください。",
        "confidence": "high",
        "line": 6,
        "target": "age",
        "related_names": [
          "user.age"
        ],
        "evidence": "user.age"
      }
    ],
    "definitions": [
      {
        "name": "__init__",
        "line": 2,
        "scope": "User@1",
        "kind": "function"
      },
      {
        "name": "self",
        "line": 2,
        "scope": "__init__@2",
        "kind": "parameter"
      },
      {
        "name": "User",
        "line": 1,
        "scope": "top@0",
        "kind": "class"
      },
      {
        "name": "user",
        "line": 5,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "self",
        "line": 3,
        "scope": "__init__@2"
      },
      {
        "name": "User",
        "line": 5,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 6,
        "scope": "top@0"
      },
      {
        "name": "user",
        "line": 6,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [
      {
        "expression": "user.age",
        "attribute": "age",
        "line": 6
      }
    ],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-035 似た変数名が複数存在

Prohibited: 特定の1候補だけが正解

{
  "explanation": {
    "summary": "Pythonが「usrname」という名前を使おうとしましたが、その場所で見つけられませんでした。",
    "cause": "変数が使用前に作られていない、スペルが違う、または使える範囲の外にある可能性があります。",
    "checkpoints": [
      "その名前を使う前に値を代入しているか確認してください。",
      "定義した名前と、大文字・小文字を含めてスペルが一致するか確認してください。",
      "関数の中で作った変数を、関数の外から使っていないか確認してください。"
    ],
    "reading_tip": "最後の行の name の後ろが、Pythonが見つけられなかった名前です。",
    "fix_example": "usrname = \"Taro\"\nprint(usrname)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "エラー行で使っている変数名を確認してください。",
    "似た名前の変数がコード内にないか探し、つづりを比べてみてください。",
    "「usrname」と「username、user_name、userName」を比較してください。タイプミスの候補ですが、意図した名前は自分で確認しましょう。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [
      {
        "kind": "undefined_name",
        "message": "「usrname」を使っていますが、このスコープから参照できる定義が貼り付けたコードには見つかりません。未定義名の候補です。",
        "confidence": "medium",
        "line": 5,
        "target": "usrname",
        "related_names": [],
        "evidence": "usrname"
      },
      {
        "kind": "similar_name",
        "message": "「usrname」に似た定義名「username、user_name、userName」があります。変数名のタイプミスの可能性があります。",
        "confidence": "medium",
        "line": 5,
        "target": "usrname",
        "related_names": [
          "username",
          "user_name",
          "userName"
        ],
        "evidence": "usrname"
      }
    ],
    "definitions": [
      {
        "name": "user_name",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "username",
        "line": 2,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "userName",
        "line": 3,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 5,
        "scope": "top@0"
      },
      {
        "name": "usrname",
        "line": 5,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-036 builtinsを未定義扱いしない

Prohibited: print が未定義 / len が未定義

{
  "explanation": {
    "summary": "ログからエラーの種類を読み取れませんでした。",
    "cause": "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
    "checkpoints": [
      "Traceback から最後のエラー行までコピーしてください。",
      "最後に「エラー種類: メッセージ」があるか確認してください。",
      "Pythonで発生したログか確認してください。"
    ],
    "reading_tip": "まず最後のエラー行、次に直前の File と line を読みます。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。",
    "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。",
    "Traceback から最後のエラー行までコピーしてください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [],
    "uses": [
      {
        "name": "print",
        "line": 1,
        "scope": "top@0"
      },
      {
        "name": "len",
        "line": 1,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "行番号が取得できないため、コードの該当行を表示できません。Traceback全体を貼り付けてください。"
  ]
}

## PY-037 import済みモジュールを未定義扱いしない

Prohibited: math が未定義 / sqrt が未定義

{
  "explanation": {
    "summary": "ログからエラーの種類を読み取れませんでした。",
    "cause": "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
    "checkpoints": [
      "Traceback から最後のエラー行までコピーしてください。",
      "最後に「エラー種類: メッセージ」があるか確認してください。",
      "Pythonで発生したログか確認してください。"
    ],
    "reading_tip": "まず最後のエラー行、次に直前の File と line を読みます。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。",
    "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。",
    "Traceback から最後のエラー行までコピーしてください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "math",
        "line": 1,
        "scope": "top@0",
        "kind": "import"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 2,
        "scope": "top@0"
      },
      {
        "name": "math",
        "line": 2,
        "scope": "top@0"
      }
    ],
    "imports": [
      {
        "module": "math",
        "imported_name": null,
        "bound_name": "math",
        "line": 1
      }
    ],
    "attributes": [
      {
        "expression": "math.sqrt",
        "attribute": "sqrt",
        "line": 2
      }
    ],
    "notes": []
  },
  "notes": [
    "行番号が取得できないため、コードの該当行を表示できません。Traceback全体を貼り付けてください。"
  ]
}

## PY-038 from import済み名称を未定義扱いしない

Prohibited: sqrt が未定義

{
  "explanation": {
    "summary": "ログからエラーの種類を読み取れませんでした。",
    "cause": "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
    "checkpoints": [
      "Traceback から最後のエラー行までコピーしてください。",
      "最後に「エラー種類: メッセージ」があるか確認してください。",
      "Pythonで発生したログか確認してください。"
    ],
    "reading_tip": "まず最後のエラー行、次に直前の File と line を読みます。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。",
    "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。",
    "Traceback から最後のエラー行までコピーしてください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "sqrt",
        "line": 1,
        "scope": "top@0",
        "kind": "import"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 2,
        "scope": "top@0"
      },
      {
        "name": "sqrt",
        "line": 2,
        "scope": "top@0"
      }
    ],
    "imports": [
      {
        "module": "math",
        "imported_name": "sqrt",
        "bound_name": "sqrt",
        "line": 1
      }
    ],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "行番号が取得できないため、コードの該当行を表示できません。Traceback全体を貼り付けてください。"
  ]
}

## PY-039 分岐次第で未定義になる変数

Prohibited: result は必ず定義済み

{
  "explanation": {
    "summary": "Pythonが「result」という名前を使おうとしましたが、その場所で見つけられませんでした。",
    "cause": "変数が使用前に作られていない、スペルが違う、または使える範囲の外にある可能性があります。",
    "checkpoints": [
      "その名前を使う前に値を代入しているか確認してください。",
      "定義した名前と、大文字・小文字を含めてスペルが一致するか確認してください。",
      "関数の中で作った変数を、関数の外から使っていないか確認してください。"
    ],
    "reading_tip": "最後の行の name の後ろが、Pythonが見つけられなかった名前です。",
    "fix_example": "result = \"Taro\"\nprint(result)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "<evaluation>/snippet.py の 6 行目付近を確認してください。文法エラーでは直前の行も見てみましょう。",
    "メッセージに出てくる「result」に注目してください。コードのどこで使っていますか？",
    "その名前を使う前に値を代入しているか確認してください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "condition",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "result",
        "line": 4,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "condition",
        "line": 3,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 6,
        "scope": "top@0"
      },
      {
        "name": "result",
        "line": 6,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-040 空ループ後の未定義変数

Prohibited: result はループ内で代入されるので安全

{
  "explanation": {
    "summary": "Pythonが「result」という名前を使おうとしましたが、その場所で見つけられませんでした。",
    "cause": "変数が使用前に作られていない、スペルが違う、または使える範囲の外にある可能性があります。",
    "checkpoints": [
      "その名前を使う前に値を代入しているか確認してください。",
      "定義した名前と、大文字・小文字を含めてスペルが一致するか確認してください。",
      "関数の中で作った変数を、関数の外から使っていないか確認してください。"
    ],
    "reading_tip": "最後の行の name の後ろが、Pythonが見つけられなかった名前です。",
    "fix_example": "result = \"Taro\"\nprint(result)",
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "<evaluation>/snippet.py の 4 行目付近を確認してください。文法エラーでは直前の行も見てみましょう。",
    "メッセージに出てくる「result」に注目してください。コードのどこで使っていますか？",
    "その名前を使う前に値を代入しているか確認してください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "x",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "result",
        "line": 2,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "x",
        "line": 2,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 4,
        "scope": "top@0"
      },
      {
        "name": "result",
        "line": 4,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。"
  ]
}

## PY-041 関数スコープとグローバルの同名変数

Prohibited: value が未定義 / スコープエラー

{
  "explanation": {
    "summary": "ログからエラーの種類を読み取れませんでした。",
    "cause": "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
    "checkpoints": [
      "Traceback から最後のエラー行までコピーしてください。",
      "最後に「エラー種類: メッセージ」があるか確認してください。",
      "Pythonで発生したログか確認してください。"
    ],
    "reading_tip": "まず最後のエラー行、次に直前の File と line を読みます。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。",
    "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。",
    "Traceback から最後のエラー行までコピーしてください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "value",
        "line": 1,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "test",
        "line": 3,
        "scope": "top@0",
        "kind": "function"
      },
      {
        "name": "value",
        "line": 4,
        "scope": "test@3",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "print",
        "line": 5,
        "scope": "test@3"
      },
      {
        "name": "value",
        "line": 5,
        "scope": "test@3"
      },
      {
        "name": "test",
        "line": 7,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 8,
        "scope": "top@0"
      },
      {
        "name": "value",
        "line": 8,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "行番号が取得できないため、コードの該当行を表示できません。Traceback全体を貼り付けてください。"
  ]
}

## PY-042 例外処理済みのZeroDivisionError

Prohibited: プログラムが ZeroDivisionError で停止する

{
  "explanation": {
    "summary": "ログからエラーの種類を読み取れませんでした。",
    "cause": "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
    "checkpoints": [
      "Traceback から最後のエラー行までコピーしてください。",
      "最後に「エラー種類: メッセージ」があるか確認してください。",
      "Pythonで発生したログか確認してください。"
    ],
    "reading_tip": "まず最後のエラー行、次に直前の File と line を読みます。",
    "fix_example": null,
    "fix_note": "入力コードを自動修正したものではなく、考え方を示す学習用の例です。"
  },
  "hints": [
    "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。",
    "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。",
    "Traceback から最後のエラー行までコピーしてください。"
  ],
  "code_analysis": {
    "status": "parsed",
    "findings": [],
    "definitions": [
      {
        "name": "x",
        "line": 2,
        "scope": "top@0",
        "kind": "assignment"
      },
      {
        "name": "x",
        "line": 4,
        "scope": "top@0",
        "kind": "assignment"
      }
    ],
    "uses": [
      {
        "name": "ZeroDivisionError",
        "line": 3,
        "scope": "top@0"
      },
      {
        "name": "print",
        "line": 6,
        "scope": "top@0"
      },
      {
        "name": "x",
        "line": 6,
        "scope": "top@0"
      }
    ],
    "imports": [],
    "attributes": [],
    "notes": []
  },
  "notes": [
    "行番号が取得できないため、コードの該当行を表示できません。Traceback全体を貼り付けてください。"
  ]
}
