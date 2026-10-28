# 学生テストの提供タスク・進行用の答え

これはPython用の提供課題です。結果はまだありません。C/C++授業の課題としては使わず、対象環境を確認してから別の課題と実ログを用意します。本人の実例を使う場合は、本人・先生の共有許可と匿名化を確認したコード・ログに限り、APIキー・成績情報などは使いません。手順と記録は[最新の調査依頼](RESEARCH_REQUEST.md)に従います。学習者には「何が起きたと思うか、次に何を確認するか、自分の言葉で説明してください」と依頼します。

## タスクA：メニューの件数

```python
def menu_count(menu):
    return len(menu)

menu = ["curry", "salad"]
print(menu_counts(menu))
```

```text
Traceback (most recent call last):
  File "menu.py", line 5, in <module>
    print(menu_counts(menu))
NameError: name 'menu_counts' is not defined
```

進行用の判定：場所は5行目。対象は呼び出している名前と定義名。次の確認は、関数定義のmenu_countと呼び出しのmenu_countsの綴りを比較すること。修正コードを丸暗記できたかは判定対象にしません。

## タスクB：送料の表示

```python
def label_shipping(cost):
    prefix = "送料: "
    return prefix + cost

print(label_shipping(500))
```

```text
Traceback (most recent call last):
  File "shipping.py", line 5, in <module>
    print(label_shipping(500))
  File "shipping.py", line 3, in label_shipping
    return prefix + cost
TypeError: can only concatenate str (not "int") to str
```

進行用の判定：失敗した操作は関数内3行目、呼び出し元は5行目。対象は文字列と数値の連結。次の確認は左右の型・costが渡される箇所を追うこと。単に500を別の数に変えるという提案は、型の問題を確かめる行動としては得点にしません。

## 実施時の注意

片方をアプリあり、もう片方をアプリなしで読みます。タスクの難しさが同じとは保証できず、短い調査でAIやアプリの因果的な効果は測れません。AIと標準ガイドを比較する場合は、同じ課題だけを繰り返して記憶で解かないよう、別途同等課題を用意してください。

模範回答を参加者に先に見せないでください。終了後の説明では、エラーの位置、根拠、次の確認という読み方を伝えて構いません。
