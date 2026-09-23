"""spec を1つ受け取って、9枚すべてを検査する

idea036 の inspect_image.py をベースに、次の2点だけ変えている。

  1. 9枚をまとめて回す（1枚ずつ叩いていたのをループにした）
  2. **verdict を持たない spec（観測のみ条件）を受け付ける**
     観測のみ条件では多数決を取らない。判断は後段（Jev / Haiku / ルール）が行う。

出力は idea036 と同じ形（final / runs / meta）にして、集計コードを共用できるようにする。

Usage:
    python scripts/run_inspection.py --spec specs/spec_A_ord.json --out results/exp2/A_ord
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

import bedrock
from add_grid import add_grid

IMAGES = [
    ("n1", "images/normal/n1.jpg"), ("n2", "images/normal/n2.jpg"),
    ("n3", "images/normal/n3.jpg"), ("n4", "images/normal/n4.jpg"),
    ("n5", "images/normal/n5.jpg"),
    ("d1_stain", "images/defect/d1_stain.jpg"), ("d2_broken", "images/defect/d2_broken.jpg"),
    ("d3_deformed", "images/defect/d3_deformed.jpg"), ("d4_bent", "images/defect/d4_bent.jpg"),
]


def build_content(spec, image_path, grid_dir):
    """正常サンプル → 検査画像 → プロンプト の順（idea036 の refs=normal と同じ構成）"""
    meta = spec["_meta"]
    cols, rows = meta["cols"], meta["rows"]

    content = [{"text": "=== 参照: 正常サンプル（これは検査対象ではありません）==="}]
    for p in meta["normal_images"]:
        content.append(bedrock.image_block(p))

    src = Path(image_path)
    grid_path = Path(grid_dir) / f"{src.stem}_grid{cols}x{rows}.png"
    grid_path.parent.mkdir(parents=True, exist_ok=True)
    add_grid(Image.open(src), cols, rows).save(grid_path)

    content.append({"text": f"=== ここから検査画像です。この画像だけを判定してください（{cols}x{rows} グリッド焼き込み済み）==="})
    content.append(bedrock.image_block(grid_path))

    schema = json.dumps(spec["output_schema"], ensure_ascii=False)
    content.append({"text": f"{spec['inspection_prompt']}\n\n【JSON スキーマ】\n{schema}"})
    return content


def vote(results, runs):
    """idea036 と同じ多数決。過半数に届かなければ安全側の REVIEW に倒す"""
    verdicts = [r["verdict"] for r in results if r and r.get("verdict")]
    if not verdicts:
        return {"verdict": "REVIEW", "cells": [], "reason": "全ての試行が失敗"}
    counts = Counter(verdicts)
    top, n = counts.most_common(1)[0]
    cell_counts = Counter(
        c for r in results if r for f in (r.get("findings") or []) for c in (f.get("cells") or [])
    )
    return {
        "verdict": top if n > runs / 2 else "REVIEW",
        "cells": sorted(c for c, k in cell_counts.items() if k > len(verdicts) / 2),
        "verdict_counts": dict(counts),
        "cell_counts": dict(cell_counts),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=bedrock.INSPECTOR_MODEL)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--grid-dir", default="out/grid")
    args = p.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    has_verdict = "verdict" in spec["output_schema"]["properties"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"spec   : {args.spec}  (variant={spec['_meta'].get('variant')})")
    print(f"model  : {args.model}   runs={args.runs}   verdict を出させる: {has_verdict}")
    print(f"キー順 : {list(spec['output_schema']['properties'].keys())}")
    print()

    t_all = time.time()
    n_fail = n_call = 0
    for name, path in IMAGES:
        content = build_content(spec, path, args.grid_dir)
        results, metas, raws = [], [], []
        for i in range(args.runs):
            text, meta = bedrock.converse(args.model, content, max_tokens=2048)
            metas.append(meta)
            # JSON の外に書かれた文章も残す。観測のみ条件でもモデルが
            # 「判定理由」を JSON の外に書くことが実測で分かったため。
            raws.append(text)
            n_call += 1
            try:
                results.append(bedrock.parse_json(text))
            except Exception as e:
                print(f"  {name} run{i + 1}: JSON パース失敗 ({type(e).__name__})")
                results.append(None)
                n_fail += 1

        final = vote(results, args.runs) if has_verdict else None
        (out / f"res_{name}.json").write_text(
            json.dumps({"final": final, "runs": results, "meta": metas, "raw": raws}, ensure_ascii=False, indent=2)
        )

        n_find = [len(r.get("findings") or []) if r else "X" for r in results]
        v = final["verdict"] if final else "-"
        print(f"  {name:<12} verdict={v:<7} findings={n_find} "
              f"avg={sum(m['seconds'] for m in metas) / len(metas):.2f}s "
              f"in={metas[0]['input_tokens']} out={sum(m['output_tokens'] for m in metas)}")

    print(f"\n合計 {n_call} コール / {time.time() - t_all:.0f}秒 / パース失敗 {n_fail}")
    print(f"保存: {out}")


if __name__ == "__main__":
    main()
