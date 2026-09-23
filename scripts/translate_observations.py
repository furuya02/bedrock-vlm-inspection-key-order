"""観測テキストを Amazon Translate で機械翻訳して、英語版の state を作る

なぜ翻訳するか:
  Jev の公式ドキュメントに「英語が主たる学習言語であり、CJK を含む他言語は
  受け付けるが現時点で精度は低い」と明記されている。idea036 の観測は日本語なので、
  このまま投げると「日本語だから落ちた」のか「判断層の分離が効かなかった」のかを
  切り分けられない。

なぜ LLM ではなく Amazon Translate か:
  LLM に訳させると要約や解釈が混入し、「観測を固定して判断層だけを差し替える」という
  実験の前提が崩れる。機械翻訳なら判断が入らない。

翻訳はユニークな文字列単位でキャッシュする（同じ文が何度も出てくるため）。

Usage:
    python scripts/translate_observations.py
"""

import argparse
import json
from pathlib import Path

import boto3

# findings の中で訳す必要があるキー（cells や confidence は訳さない）
FINDING_TEXT_KEYS = ["defect_type", "evidence", "difference_from_normal", "reason"]
TOP_TEXT_KEYS = ["normal_observations", "overall_notes", "symmetry_check"]


# 翻訳前に日本語側を正規化する語
#
# 素の Amazon Translate に投げると検査用語が壊れた。実測した例:
#   「外縁・内縁とも連続した曲線」
#       → "continuous curves for both outer marriage and common law marriage"
#         （「縁」を婚姻関係と解釈された）
#   「脚先」        → "the tip of the foot"
#   「ガタガタした欠け」→ "rattling chips"
#   「白飛びハイライト」→ "white skipping highlights"
#
# カスタム用語集（import_terminology）も試したが、「外縁」だけが置換されて
# "outer edge marriage and common law marriage" になり直りきらなかった。
# 原因は日本語側の多義性なので、訳す前に日本語を言い換える方が確実だった。
# 素の訳は results/translations_raw.json / observations_en_raw.json に残してある。
NORMALIZE = {
    "外縁": "外側の縁",
    "内縁": "内側の縁",
    "脚先": "脚の先端",
    "ガタガタ": "ギザギザ",
    "白飛び": "露出オーバー",
}


def normalize_ja(text):
    for a, b in NORMALIZE.items():
        text = text.replace(a, b)
    return text


def translator(region, normalize=True):
    client = boto3.client("translate", region_name=region)
    cache = {}

    def tr(text):
        if not isinstance(text, str) or not text.strip():
            return text
        if text not in cache:
            src = normalize_ja(text) if normalize else text
            cache[text] = client.translate_text(
                Text=src, SourceLanguageCode="ja", TargetLanguageCode="en"
            )["TranslatedText"]
        return cache[text]

    return tr, cache


def translate_state(state, tr):
    out = {}
    for k, v in state.items():
        if k == "findings":
            out[k] = [
                {kk: (tr(vv) if kk in FINDING_TEXT_KEYS else vv) for kk, vv in f.items()}
                for f in v
            ]
        elif k in TOP_TEXT_KEYS:
            out[k] = tr(v)
        else:
            out[k] = v
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="results/observations.json")
    p.add_argument("--out", default="results/observations_en.json")
    p.add_argument("--cache", default="results/translations.json")
    p.add_argument("--region", default="ap-northeast-1")
    p.add_argument("--raw", action="store_true", help="日本語の正規化をせず素のまま訳す")
    args = p.parse_args()

    tasks = json.loads(Path(args.src).read_text())
    tr, cache = translator(args.region, normalize=not args.raw)

    out = []
    for t in tasks:
        t2 = dict(t)
        t2["lang"] = "en"
        t2["state"] = translate_state(t["state"], tr)
        out.append(t2)

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    Path(args.cache).write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    chars = sum(len(k) for k in cache)
    print(f"タスク数           : {len(out)}")
    print(f"ユニーク翻訳文字列 : {len(cache)}")
    print(f"翻訳した文字数     : {chars:,}  （Amazon Translate は $15 / 100万文字）")
    print(f"概算費用           : ${chars * 15 / 1_000_000:.4f}")
    print(f"出力               : {args.out}")
    print(f"翻訳キャッシュ     : {args.cache}")


if __name__ == "__main__":
    main()
