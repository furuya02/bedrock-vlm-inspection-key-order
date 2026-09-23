"""Jev の疎通確認

確認したいこと:
  1. Vercel AI Gateway 経由で Jev に届くか
  2. 短い「日本語」の state を扱えるか（公式は「CJK は精度が低い」と明記している）
  3. Choice / Score / Noul が実際にどう返るか（Noul に confidence が無いことの確認を含む）
  4. 同じ内容を英語にすると答えが変わるか
  5. TypeSafe 互換 API と Gateway 独自 API で返りの形がどう違うか
  6. 1リクエストの実費とレイテンシ

Usage:
    python scripts/check_jev.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import jev

OUT = Path(__file__).parent.parent / "results" / "connectivity"

# 洗濯ばさみの検査という本番と同じ土俵で、かつ十分に短い state
STATES = {
    "defect_ja": "洗濯ばさみの先端のつまみ部が折れて欠けている。破断面がガタガタしている。",
    "defect_en": "The tip of the clothespin is broken and chipped. The fracture surface is jagged.",
    "normal_ja": "洗濯ばさみの先端は左右対称で揃っており、破断面や欠けはない。脚の形状も正常。",
    "normal_en": "The clothespin tips are symmetrical and aligned, with no fracture or chipping. The legs are normal.",
}

QUESTIONS_JA = {
    "verdict": jev.choice(
        "この検査対象をどう判定するか",
        {"OK": "欠陥なし", "REVIEW": "人が目視で確認すべき", "NG": "明らかな欠陥がある"},
    ),
    "has_defect": jev.noul("この検査対象には欠陥がある"),
    "severity": jev.score("欠陥の程度", ["欠陥なし", "軽微", "明らかな欠陥"]),
}

QUESTIONS_EN = {
    "verdict": jev.choice(
        "How should this inspected item be judged",
        {"OK": "no defect", "REVIEW": "a human should visually confirm", "NG": "there is a clear defect"},
    ),
    "has_defect": jev.noul("This inspected item has a defect"),
    "severity": jev.score("Severity of the defect", ["no defect", "minor", "clear defect"]),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    saved = {}

    print("=" * 78)
    print("A: TypeSafe 互換 API  POST /typesafe/v1/systemone")
    print("=" * 78)
    for name, state in STATES.items():
        questions = QUESTIONS_JA if name.endswith("_ja") else QUESTIONS_EN
        res, elapsed = jev.system_one(state, questions)
        saved[f"A_{name}"] = res
        a = res["answers"]
        print(f"\n--- {name}  ({elapsed * 1000:.0f} ms)")
        print(f"  state    : {state}")
        print(f"  model    : {res.get('model')}")
        print(f"  choice   : {a['verdict'].get('choice')}  "
              f"conf={a['verdict'].get('confidence')}  probs={a['verdict'].get('probabilities')}")
        print(f"  noul     : {a['has_defect'].get('noul')}  "
              f"(confidence キーの有無: {'has_defect に confidence あり' if 'confidence' in a['has_defect'] else 'なし'})")
        print(f"  score    : {a['severity'].get('score')}  probs={a['severity'].get('probabilities')}")
        print(f"  usage    : {res.get('usage')}   cost={jev.cost_of(res)}")

    print()
    print("=" * 78)
    print("B: Gateway 独自 API  POST /v1/evaluate  （返りの形の違いを記録するため1回だけ）")
    print("=" * 78)
    res, elapsed = jev.evaluate(
        STATES["defect_ja"],
        {
            "has_defect": {"type": "boolean", "instructions": "この検査対象には欠陥がある"},
            "verdict": QUESTIONS_JA["verdict"],
        },
    )
    saved["B_defect_ja"] = res
    print(f"\n--- defect_ja  ({elapsed * 1000:.0f} ms)")
    print(json.dumps(res, ensure_ascii=False, indent=2))

    for k, v in saved.items():
        (OUT / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
    print(f"\n保存: {OUT}  ({len(saved)} ファイル)")


if __name__ == "__main__":
    main()
