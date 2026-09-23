"""idea036 の実行結果から「観測」だけを取り出して、Jev に渡す state を作る

idea036 の結果 JSON には verdict（VLM 自身の判断）と findings / normal_observations
（観測）が両方入っている。verdict を捨てれば、観測を固定したまま判断層だけを
差し替えた比較ができる。

state は2種類作る。公式ドキュメントが
「判断に無関係な内容で state が長くなると精度が落ちる。無関係な detail は distractor として働く」
と明記しているため、normal_observations を入れた場合と入れない場合を分ける。

  full          … findings + normal_observations + overall_notes + symmetry_check
  findings_only … findings だけ

判定の粒度は idea036 に合わせて run 単位（後で3回多数決を取る）。

Usage:
    python scripts/extract_observations.py
    python scripts/extract_observations.py --src /path/to/idea036/.../results --out results/observations.json
"""

import argparse
import json
from pathlib import Path

# idea036 の結果はこのリポジトリに持ち込み済み（出典は results/idea036/SOURCE.md）
DEFAULT_SRC = Path(__file__).resolve().parent.parent / "results" / "idea036"

CONDITIONS = {"A_haiku": "haiku", "A_nova": "nova", "B": "partB", "C": "partC"}
IMAGES = ["n1", "n2", "n3", "n4", "n5", "d1_stain", "d2_broken", "d3_deformed", "d4_bent"]
OBS_KEYS = ["findings", "normal_observations", "overall_notes", "symmetry_check"]


def states_of(run):
    """1 run 分の観測から2種類の state を作る（verdict は必ず捨てる）"""
    full = {k: run[k] for k in OBS_KEYS if run.get(k)}
    full.setdefault("findings", [])
    return {"full": full, "findings_only": {"findings": full["findings"]}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default=str(DEFAULT_SRC))
    p.add_argument("--out", default="results/observations.json")
    args = p.parse_args()

    src = Path(args.src)
    tasks, skipped = [], 0

    for cond, sub in CONDITIONS.items():
        for img in IMAGES:
            f = src / sub / f"res_{img}.json"
            if not f.exists():
                continue
            data = json.loads(f.read_text())
            for i, run in enumerate(data["runs"]):
                if run is None:  # idea036 で JSON パースに失敗した run
                    skipped += 1
                    continue
                for variant, state in states_of(run).items():
                    tasks.append({
                        "condition": cond,
                        "image": img,
                        "truth": "normal" if img.startswith("n") else "defect",
                        "run": i,
                        "variant": variant,
                        "lang": "ja",
                        "vlm_verdict": run.get("verdict"),  # 比較用。state には入れない
                        "state": state,
                    })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))

    n_empty = sum(1 for t in tasks if t["variant"] == "findings_only" and not t["state"]["findings"])
    n_fi = sum(1 for t in tasks if t["variant"] == "findings_only" and t["state"]["findings"])
    print(f"タスク数           : {len(tasks)}")
    print(f"  うち findings 非空: {n_fi}（findings_only 条件）")
    print(f"  うち findings 空  : {n_empty}（findings_only 条件・判定材料が無い）")
    print(f"パース失敗でスキップ: {skipped} run")
    print(f"出力               : {out}")


if __name__ == "__main__":
    main()
