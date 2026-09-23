"""観測だけを受け取って OK / REVIEW / NG を決める判断層

同じ観測に対して判断層だけを差し替えて比較する。VLM は再実行しない。

  rule  … findings が空でなければ NG。空なら OK（判断にモデルを使わない下限）
  haiku … Claude Haiku 4.5 に観測を**テキストだけ**渡して判定させる（画像は渡さない）
  jev   … Jev（System One モデル）に渡す。AI_GATEWAY_API_KEY が要る

3つとも同じ観測・同じ3回多数決で比べる。差が出るのは判断層だけ。

判定基準の文面は idea036 の検査プロンプトからそのまま持ってきている。
判断層の違いだけを見たいので、基準を書き換えてはいけない。

Usage:
    python scripts/judge_observations.py --src results/exp2/A_obs --judge rule
    python scripts/judge_observations.py --src results/exp2/A_obs --judge haiku
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bedrock

IMAGES = ["n1", "n2", "n3", "n4", "n5", "d1_stain", "d2_broken", "d3_deformed", "d4_bent"]

# idea036 の検査プロンプトの「■ 判定」節をそのまま使う
CRITERIA = """・OK = 欠陥なし。
・REVIEW = 欠陥かどうか判断がつかない、影や光沢と区別できない、部分的に隠れて確認できない。
・NG = 明らかな欠陥がある（破断面が見える欠け、明確な切り欠き、明らかな変形・ねじれ、はっきりした穴や異物）。
迷ったら NG ではなく REVIEW にしてください。"""

HAIKU_PROMPT = """あなたは外観検査の判定担当です。検査員が記録した観測所見だけを読んで、合否を判定してください。
画像は渡されません。所見に書かれていないことを推測しないでください。

■ 判定
{criteria}

■ 観測所見
{observation}

■ 出力
{{"verdict": "OK" | "REVIEW" | "NG"}} の形の純粋な JSON のみを出力してください。"""


def judge_rule(obs):
    return "NG" if obs.get("findings") else "OK"


# Jev に投げる質問。判定基準の文言は CRITERIA と揃える（判断層だけを変えるため）
JEV_QUESTIONS = {
    "ja": {
        "verdict": {"type": "choice", "instructions": "この検査所見から、検査対象をどう判定するか",
                    "criteria": {"OK": "欠陥なし",
                                 "REVIEW": "欠陥かどうか判断がつかない、影や光沢と区別できない、部分的に隠れて確認できない",
                                 "NG": "明らかな欠陥がある（破断面が見える欠け、明確な切り欠き、明らかな変形・ねじれ、はっきりした穴や異物）"}},
        "has_defect": {"type": "noul", "instructions": "この検査対象には欠陥がある"},
        "severity": {"type": "score", "instructions": "欠陥の程度",
                     "criteria": ["欠陥なし", "軽微", "明らかな欠陥"]},
    },
    "en": {
        "verdict": {"type": "choice", "instructions": "Based on these inspection observations, how should the item be judged",
                    "criteria": {"OK": "no defect",
                                 "REVIEW": "cannot tell whether it is a defect, cannot distinguish it from shadow or gloss, or it is partly hidden",
                                 "NG": "there is a clear defect (a chip with a visible fracture surface, a clear notch, clear deformation or twist, a distinct hole or foreign object)"}},
        "has_defect": {"type": "noul", "instructions": "This inspected item has a defect"},
        "severity": {"type": "score", "instructions": "Severity of the defect",
                     "criteria": ["no defect", "minor", "clear defect"]},
    },
}


def judge_jev(obs, lang="ja", dry_run=False):
    """観測を state にして Jev に投げる。Choice / Noul / Score を1往復でまとめて取る"""
    import jev as jev_client

    questions = JEV_QUESTIONS[lang]
    if dry_run:
        return None, {"state": obs, "questions": questions, "model": jev_client.MODEL}

    res, elapsed = jev_client.system_one(obs, questions)
    a = res["answers"]
    meta = {
        "seconds": round(elapsed, 3),
        "input_tokens": (res.get("usage") or {}).get("input_tokens"),
        "output_tokens": (res.get("usage") or {}).get("output_tokens"),
        "confidence": a["verdict"].get("confidence"),
        "probabilities": a["verdict"].get("probabilities"),
        "noul": a["has_defect"].get("noul"),
        "score": a["severity"].get("score"),
        "cost": jev_client.cost_of(res),
        "model": res.get("model"),
    }
    return a["verdict"].get("choice"), meta


def judge_haiku(obs):
    text = HAIKU_PROMPT.format(
        criteria=CRITERIA, observation=json.dumps(obs, ensure_ascii=False, indent=1)
    )
    out, meta = bedrock.converse(bedrock.INSPECTOR_MODEL, [{"text": text}], max_tokens=256)
    try:
        return bedrock.parse_json(out).get("verdict"), meta
    except Exception:
        return None, meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True)
    p.add_argument("--judge", required=True, choices=["rule", "haiku", "jev"])
    p.add_argument("--lang", default="ja", choices=["ja", "en"], help="jev のときの質問文の言語")
    p.add_argument("--dry-run", action="store_true", help="API を叩かず、送るペイロードだけ表示する")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    src = Path(args.src)
    out = Path(args.out or f"{src}_judged_{args.judge}.json")
    results, metas = {}, []

    for name in IMAGES:
        f = src / f"res_{name}.json"
        data = json.loads(f.read_text())
        verdicts = []
        for run in data["runs"]:
            if run is None:
                verdicts.append(None)
                continue
            if args.judge == "rule":
                verdicts.append(judge_rule(run))
            elif args.judge == "haiku":
                v, meta = judge_haiku(run)
                metas.append(meta)
                verdicts.append(v)
            else:
                v, meta = judge_jev(run, args.lang, args.dry_run)
                metas.append(meta)
                verdicts.append(v)

        valid = [v for v in verdicts if v]
        counts = Counter(valid)
        top, n = counts.most_common(1)[0] if valid else ("REVIEW", 0)
        final = top if n > len(data["runs"]) / 2 else "REVIEW"
        results[name] = {"verdict": final, "runs": verdicts, "counts": dict(counts)}
        print(f"  {name:<12} {final:<7} {verdicts}")

    if args.dry_run:
        print("\n--- 送信するペイロードの例（先頭1件）---")
        print(json.dumps(metas[0], ensure_ascii=False, indent=2)[:1400])
        return

    summary = {"src": str(src), "judge": args.judge, "results": results,
               "detail": metas if args.judge == "jev" else None}
    if metas:
        summary["seconds_avg"] = round(sum(m["seconds"] for m in metas) / len(metas), 3)
        summary["input_tokens_total"] = sum(m.get("input_tokens") or 0 for m in metas)
        summary["output_tokens_total"] = sum(m.get("output_tokens") or 0 for m in metas)
        print(f"\n  平均 {summary['seconds_avg']}秒/回  "
              f"in={summary['input_tokens_total']} out={summary['output_tokens_total']}")
        if args.judge == "jev":
            import jev as jev_client
            summary["retries"] = jev_client.retry_log
            if jev_client.retry_log:
                from collections import Counter as _C
                print(f"  リトライ: {dict(_C(x['status'] for x in jev_client.retry_log))}")
            costs = [float(m["cost"]) for m in metas if m.get("cost")]
            print(f"  Jev 実費 合計 ${sum(costs):.6f}（{len(costs)} リクエスト）")
            print(f"  confidence: {[m.get('confidence') for m in metas[:6]]} …")

    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"保存: {out}")


if __name__ == "__main__":
    main()
