# 検査プロンプト（idea036 の3条件）

前回の記事で比較した3つの検査条件です。本リポジトリの実験は、この3条件を出発点にしています。

| 条件 | 内容 | 出力スキーマのキー順 | 検出（REVIEW以上）/ 異常4枚 | 過検出 / 正常5枚 |
|---|---|---|---:|---:|
| [A 欠陥の記述のみ](A_description_only.md) | 欠陥6種類の見た目を具体的に記述 | verdict → findings → … | 2 | 0 |
| [B 検査手順のみ](B_steps_only.md) | 記述を削り手順を前面に出す | symmetry_check → verdict → findings | 0 | 0 |
| [C 記述 + 手順](C_description_and_steps.md) | A に手順4ステップを追加 | verdict → findings → … | 0 | 0 |

3条件とも `verdict` が `findings` より先に定義されています。
本リポジトリでは、この並びを `findings → verdict` に入れ替えた spec を `specs/` に生成し、
検出率がどう変わるかを比較しています。

変換スクリプト: [`scripts/make_specs.py`](../scripts/make_specs.py)
