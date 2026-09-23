"""実験1: 観測（verdict を除いたもの）を Jev に渡して判定させる

extract_observations.py / translate_observations.py が作ったタスクを読み、
Choice（OK/REVIEW/NG）と Noul（欠陥があるか）と Score（程度）を
**1リクエストに同居させて**投げる。公式が「複数の質問は1往復で並列に答えられる」と
書いているので、3問でも1回で済む。

同じ state が何度も出てくる（findings が空のケースが101件ある）ので、
state の内容でハッシュを取って重複を1回にまとめる。

Usage:
    python scripts/run_jev.py                      # 日本語
    python scripts/run_jev.py --src results/observations_en.json --lang en
    python scripts/run_jev.py --determinism 5      # 同じ state を5回投げて決定性を見る
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import jev

# 質問文は judge_observations.py と共有する。
# 当初 run_jev.py だけ criteria を短く言い換えていたが、それだと実験1と実験2③が
# 比較できない（実測で、criteria の言い回しだけで確率が変わることを確認した）。
from judge_observations import JEV_QUESTIONS as QUESTIONS


def key_of(state):
    return hashlib.sha256(json.dumps(state, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="results/observations.json")
    p.add_argument("--lang", default="ja", choices=["ja", "en"])
    p.add_argument("--out", default=None)
    p.add_argument("--determinism", type=int, default=0, help="同じ state を何回投げるか（0で無効）")
    args = p.parse_args()

    tasks = json.loads(Path(args.src).read_text())
    questions = QUESTIONS[args.lang]
    out = Path(args.out or f"results/jev_exp1_{args.lang}.json")

    # ★ 重複をまとめてはいけない。
    # 当初は同じ state を1回だけ投げて結果を使い回していたが、Jev の確率値は
    # 非決定的で、判定が割れる境界付近では 1 回の抽選結果に引きずられる。
    # idea036 と同じ「3回投げて多数決」を成立させるため、タスクごとに投げる。
    total_cost, total_ms = 0.0, 0.0
    results = []
    for i, t in enumerate(tasks, 1):
        res, elapsed = jev.system_one(t["state"], questions)
        total_ms += elapsed * 1000
        c = jev.cost_of(res)
        total_cost += float(c or 0)
        results.append(dict(t, jev={"answers": res["answers"], "usage": res.get("usage"),
                                    "model": res.get("model"), "cost": c,
                                    "ms": round(elapsed * 1000, 1)}))
        if i % 10 == 0 or i == len(tasks):
            print(f"  [{i}/{len(tasks)}] "
                  f"choice={res['answers']['verdict'].get('choice')} "
                  f"conf={res['answers']['verdict'].get('confidence')} "
                  f"({elapsed * 1000:.0f}ms)", flush=True)

    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nリクエスト数: {len(tasks)}   合計 ${total_cost:.6f}   "
          f"平均 {total_ms / max(len(tasks), 1):.0f}ms")
    if jev.retry_log:
        from collections import Counter as _C
        print(f"リトライ: {dict(_C(x['status'] for x in jev.retry_log))}")
    print(f"出力: {out}")

    if args.determinism:
        state = tasks[0]["state"]
        print(f"\n=== 決定性チェック: 同じ state を {args.determinism} 回 ===")
        seen = set()
        for i in range(args.determinism):
            res, ms = jev.system_one(state, questions)
            v = res["answers"]["verdict"]
            seen.add((v.get("choice"), v.get("confidence")))
            print(f"  {i + 1}: {v.get('choice')} conf={v.get('confidence')} "
                  f"noul={res['answers']['has_defect'].get('noul')} ({ms * 1000:.0f}ms)")
        print(f"  → {'決定的' if len(seen) == 1 else f'非決定的（{len(seen)} 通り）'}")


if __name__ == "__main__":
    main()
