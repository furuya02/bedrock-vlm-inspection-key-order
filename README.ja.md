# bedrock-vlm-inspection-key-order

Amazon Bedrock の VLM を使った外観検査で、出力スキーマのキーの並び順が検出率に与える影響を調べたコードとデータです。

前回の記事で、検査プロンプトを改善したら検出できていた欠陥まで検出できなくなる、という結果が出ました。
原因を調べたところ、出力スキーマで `verdict`（判定）を `findings`（所見）より先に定義していたことが影響していました。

- ブログ: （公開後に URL を記載）
- 前回の記事: [[Amazon Bedrock] 洗濯ばさみで外観検査AIを試してみました](https://dev.classmethod.jp/articles/bedrock-vlm-visual-inspection-clothespin/)

## 分かったこと

| 条件 | 変えたところ | A の検出/4 | B の検出/4 | C の検出/4 | 過検出/5 |
|---|---|---:|---:|---:|---:|
| 前回のまま | — | 2 | 0 | 0 | 0 |
| キー順の入れ替え | スキーマの並びだけ。検査プロンプト本文は変更なし | 3 | 3 | 2 | 0 |
| 観測と判断の分離（ルール / Haiku / Jev） | VLM に判定を出させない | 3 / 3 / 3 | 2 / 1 / 1 | 3 / 3 / 3 | 0 |

キー順の入れ替えは3条件すべてで効きました。観測と判断を分けると A と C はさらに上がりましたが、
B では所見の `reason` 欄に「欠陥と見なさないものに該当する」という判定が紛れ込み、下がりました。

## 検査プロンプト

前回の3条件は [`prompts/`](prompts/) に読める形で置いてあります。

| 条件 | 内容 | 出力スキーマのキー順 |
|---|---|---|
| [A 欠陥の記述のみ](prompts/A_description_only.md) | 欠陥6種類の見た目を具体的に記述 | verdict → findings → … |
| [B 検査手順のみ](prompts/B_steps_only.md) | 記述を削り手順を前面に出す | symmetry_check → verdict → findings |
| [C 記述 + 手順](prompts/C_description_and_steps.md) | A に手順4ステップを追加 | verdict → findings → … |

## 構成

```
.
├── prompts/     前回の3条件の検査プロンプト（読む用）
├── specs/       本リポジトリで生成した spec（キー順入れ替え / 観測のみ）
├── scripts/     実行スクリプト
├── results/
│   ├── idea036/ 前回の結果（出典は results/idea036/SOURCE.md）
│   └── exp2/    今回の実測結果
└── images/      洗濯ばさみ 正常5枚 / 異常4枚
```

## 環境

| 項目 | 値 |
|---|---|
| 目（VLM） | Amazon Bedrock `jp.anthropic.claude-haiku-4-5-20251001-v1:0` |
| リージョン | ap-northeast-1 |
| 判断（Jev） | `typesafe-ai/jev` via Vercel AI Gateway |
| Python | 3.10.13 |

AWS リソースは作成しません。Bedrock / Amazon Translate の API を呼ぶだけです。

## セットアップ

```bash
$ git clone https://github.com/furuya02/bedrock-vlm-inspection-key-order.git
$ cd bedrock-vlm-inspection-key-order
$ pip install -r requirements.txt
```

AWS の認証情報を環境変数に設定します。Bedrock で Claude Haiku 4.5 が有効になっている必要があります。

```bash
$ export AWS_DEFAULT_REGION=ap-northeast-1
```

Jev を使う場合のみ、リポジトリのルートに `.env` を置きます。
Vercel AI Gateway の API キーです（無料枠でもカード登録が必要です）。

```
AI_GATEWAY_API_KEY=xxxxxxxx
```

## 動作確認

### 1. spec を生成する

前回の spec から、キー順を入れ替えたものと、判定を出させないものを機械的に作ります。

```bash
$ python scripts/make_specs.py
--- C  元 : ['verdict', 'findings', 'normal_observations', ...]
       ord: ['findings', 'verdict', 'normal_observations', ...]
       ord のプロンプトは原文と同一か: True
```

`ord のプロンプトは原文と同一か: True` は、変えたのがキーの並びだけであることの確認です。

### 2. 検査を実行する

9枚を3回ずつ検査します。1条件あたり 27 コール、約 $0.27 です。

```bash
$ python scripts/run_inspection.py --spec specs/spec_C_ord.json --out results/exp2/C_ord
```

### 3. 判断層を差し替える

観測だけを渡して合否を決めます。VLM は再実行しません。

```bash
$ python scripts/judge_observations.py --src results/exp2/C_obs --judge rule
$ python scripts/judge_observations.py --src results/exp2/C_obs --judge haiku
$ python scripts/judge_observations.py --src results/exp2/C_obs --judge jev
```

### 4. 集計する

```bash
$ python scripts/aggregate.py
```

## 費用

記事の検証でかかった実費です。

| 項目 | 金額 |
|---|---|
| Amazon Bedrock（162 コール） | $1.537 |
| Amazon Translate（16,163 文字 × 2回） | $0.48 |
| Jev | $0（無料クレジット内） |

## ライセンス

MIT License
