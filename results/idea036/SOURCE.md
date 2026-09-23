# このフォルダのデータの出典

ここに入っているものは**本リポジトリで新たに取得したものではない**。
すべて前記事（idea036）の実行結果をそのまま持ち込んだもの。

| パス | 内容 |
|---|---|
| `haiku/` | 条件A（記述のみ）を Claude Haiku 4.5 で実行した結果（9枚 × 3 run） |
| `nova/` | 条件A を Amazon Nova 2 Lite で実行した結果 |
| `partB/` | 条件B（手順のみ）を Haiku 4.5 で実行した結果 |
| `partC/` | 条件C（記述+手順）を Haiku 4.5 で実行した結果 |
| `spec_clothespin_4x4.json` | 条件A の検査プロンプトと出力スキーマ |
| `spec_clothespin_partB.json` | 条件B の同上 |
| `spec_clothespin_partC.json` | 条件C の同上 |

`../../images/` の画像9枚（正常5・異常4）も同じ出典。

**本記事はこのデータを「判断層だけを差し替える比較」の固定入力として使う。**
観測（`findings` / `normal_observations`）を固定し、`verdict` を捨てて別の判断層に渡すことで、
目（VLM）の性能を変えずに判断層の効果だけを測れる。
