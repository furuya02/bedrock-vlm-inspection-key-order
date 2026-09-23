"""実験2 の結果を1枚の表にまとめる

検出の定義は idea036 と同じ「REVIEW 以上」。
過検出は正常5枚のうち OK 以外になった枚数。
"""

import json
from collections import Counter
from pathlib import Path

NORMALS = ["n1", "n2", "n3", "n4", "n5"]
DEFECTS = ["d1_stain", "d2_broken", "d3_deformed", "d4_bent"]
TRUTH = {
    "d1_stain": "汚れ（その他の表面欠陥）",
    "d2_broken": "破損（先端の折れ欠け）",
    "d3_deformed": "変形（ねじれ）",
    "d4_bent": "曲がり",
}


def load_dir(d):
    return {n: json.loads((Path(d) / f"res_{n}.json").read_text())
            for n in NORMALS + DEFECTS if (Path(d) / f"res_{n}.json").exists()}


def verdicts_from_runs(data):
    return {n: (v["final"]["verdict"] if v.get("final") else None) for n, v in data.items()}


def verdicts_from_judge(path):
    j = json.loads(Path(path).read_text())
    return {n: r["verdict"] for n, r in j["results"].items()}, j


def score(v):
    det = sum(1 for n in DEFECTS if v.get(n) in ("REVIEW", "NG"))
    fp = sum(1 for n in NORMALS if v.get(n) not in ("OK", None))
    return det, fp


def cost_of(data, in_rate=1.0, out_rate=5.0):
    """Bedrock の Claude Haiku 4.5: 入力 $1.00 / 出力 $5.00 per 1M tokens"""
    ti = sum(m["input_tokens"] for v in data.values() for m in v["meta"])
    to = sum(m["output_tokens"] for v in data.values() for m in v["meta"])
    sec = sum(m["seconds"] for v in data.values() for m in v["meta"])
    n_img = len(data)
    return ti, to, (ti * in_rate + to * out_rate) / 1_000_000, sec / n_img


rows = []

# ① idea036（既存データ）
for tag, d in [("① 現状 A（idea036）", "results/idea036/haiku"),
               ("① 現状 C（idea036）", "results/idea036/partC")]:
    data = load_dir(d)
    v = verdicts_from_runs(data)
    det, fp = score(v)
    ti, to, cost, sec = cost_of(data)
    fails = sum(1 for x in data.values() for r in x["runs"] if r is None)
    rows.append((tag, "VLM 自身", det, fp, sec, cost, fails, v))

# ② 順序入替
for tag, d in [("② 順序入替 A", "results/exp2/A_ord"), ("② 順序入替 C", "results/exp2/C_ord")]:
    data = load_dir(d)
    v = verdicts_from_runs(data)
    det, fp = score(v)
    ti, to, cost, sec = cost_of(data)
    fails = sum(1 for x in data.values() for r in x["runs"] if r is None)
    rows.append((tag, "VLM 自身", det, fp, sec, cost, fails, v))

# ③④⑤ 観測のみ（VLM 実行は共通、判断層だけ差し替え）
for src, label in [("results/exp2/A_obs", "A"), ("results/exp2/C_obs", "C")]:
    data = load_dir(src)
    ti, to, vlm_cost, vlm_sec = cost_of(data)
    fails = sum(1 for x in data.values() for r in x["runs"] if r is None)
    for judge, mark in [("rule", "⑤ 観測のみ+ルール"), ("haiku", "④ 観測のみ+Haikuテキスト")]:
        f = f"{src}_judged_{judge}.json"
        if not Path(f).exists():
            continue
        v, j = verdicts_from_judge(f)
        det, fp = score(v)
        jc = 0.0 if judge == "rule" else (j["input_tokens_total"] + j["output_tokens_total"] * 5) / 1_000_000
        jsec = 0.0 if judge == "rule" else j["seconds_avg"] * 3
        rows.append((f"{mark} {label}", judge, det, fp, vlm_sec + jsec, vlm_cost + jc, fails, v))

print("=" * 108)
print(f"{'条件':<26}{'判断層':<14}{'検出/4':>7}{'過検出/5':>9}{'秒/枚':>9}{'$/9枚':>10}{'パース失敗':>10}")
print("=" * 108)
for tag, judge, det, fp, sec, cost, fails, v in rows:
    print(f"{tag:<26}{judge:<14}{det:>7}{fp:>9}{sec:>9.2f}{cost:>10.4f}{fails:>10}")
print("=" * 108)

print("\n■ 画像ごとの判定")
hdr = f"{'条件':<26}" + "".join(f"{n:<13}" for n in DEFECTS)
print(hdr)
for tag, judge, det, fp, sec, cost, fails, v in rows:
    print(f"{tag:<26}" + "".join(f"{str(v.get(n)):<13}" for n in DEFECTS))

print("\n■ 報告された欠陥種別（観測のみ条件・run0）")
for src in ["results/exp2/A_obs", "results/exp2/C_obs"]:
    print(f"  [{src}]")
    for n in DEFECTS:
        f = Path(src) / f"res_{n}.json"
        r = json.loads(f.read_text())["runs"][0]
        types = [x.get("defect_type") for x in (r.get("findings") or [])]
        mark = "正解:" + TRUTH[n]
        print(f"    {n:<12} {mark:<26} 報告: {types if types else '（なし）'}")

total = sum(r[5] for r in rows if r[0].startswith(("②", "③", "④", "⑤")))
print(f"\n今回 Bedrock で発生した費用の合計（②③④⑤）: 約 ${total:.3f}")
