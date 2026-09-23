"""実験1（既存観測を Jev に渡す）と実験3（confidence）の集計"""

import json
from collections import Counter, defaultdict
from pathlib import Path

NORMALS = ["n1", "n2", "n3", "n4", "n5"]
DEFECTS = ["d1_stain", "d2_broken", "d3_deformed", "d4_bent"]


def load(lang):
    return json.loads(Path(f"results/jev_exp1_{lang}.json").read_text())


def majority(vs):
    valid = [v for v in vs if v]
    if not valid:
        return "REVIEW"
    top, n = Counter(valid).most_common(1)[0]
    return top if n > len(vs) / 2 else "REVIEW"


print("=" * 96)
print("実験1: idea036 の既存観測を Jev に渡す（VLM 再実行なし）")
print("=" * 96)
print(f"{'条件':<10}{'state':<16}{'言語':<6}{'検出/4':>7}{'過検出/5':>9}   {'画像ごと（異常4枚）'}")
print("-" * 96)

rows = []
for lang in ["ja", "en"]:
    tasks = load(lang)
    g = defaultdict(list)
    for t in tasks:
        g[(t["condition"], t["variant"], t["image"])].append(t["jev"]["answers"]["verdict"]["choice"])
    conds = sorted({k[0] for k in g})
    for cond in conds:
        for var in ["full", "findings_only"]:
            v = {img: majority(g[(cond, var, img)]) for img in NORMALS + DEFECTS if (cond, var, img) in g}
            if not v:
                continue
            det = sum(1 for n in DEFECTS if v.get(n) in ("REVIEW", "NG"))
            fp = sum(1 for n in NORMALS if v.get(n) != "OK")
            detail = " ".join(f"{n.split('_')[0]}:{v.get(n)}" for n in DEFECTS)
            print(f"{cond:<10}{var:<16}{lang:<6}{det:>7}{fp:>9}   {detail}")
            rows.append((cond, var, lang, det, fp))

print()
print("=" * 96)
print("実験3: confidence と Choice / Noul の一致")
print("=" * 96)

bands = defaultdict(lambda: [0, 0])
agree = [0, 0]
noul_vals = defaultdict(list)

for lang in ["ja", "en"]:
    for t in load(lang):
        a = t["jev"]["answers"]
        choice, conf = a["verdict"]["choice"], a["verdict"]["confidence"]
        noul = a["has_defect"]["noul"]
        truth_defect = t["truth"] == "defect"
        # Choice の正誤: 異常なら REVIEW/NG が正、正常なら OK が正
        correct = (choice in ("REVIEW", "NG")) == truth_defect
        b = "0.9-1.0" if conf >= 0.9 else "0.7-0.9" if conf >= 0.7 else "0.5-0.7" if conf >= 0.5 else "<0.5"
        bands[b][0] += 1
        bands[b][1] += int(correct)
        # Choice（NG/REVIEW）と Noul（>0.5）が一致するか
        agree[0] += 1
        agree[1] += int((choice in ("NG", "REVIEW")) == (noul > 0.5))
        noul_vals["defect" if truth_defect else "normal"].append(noul)

print(f"{'confidence 帯':<14}{'件数':>6}{'正解':>6}{'正解率':>9}")
for b in ["0.9-1.0", "0.7-0.9", "0.5-0.7", "<0.5"]:
    n, c = bands[b]
    if n:
        print(f"{b:<14}{n:>6}{c:>6}{c / n * 100:>8.1f}%")

print(f"\nChoice（NG/REVIEW）と Noul（>0.5）の一致: {agree[1]}/{agree[0]} = {agree[1] / agree[0] * 100:.1f}%")
for k, vs in noul_vals.items():
    print(f"  noul の平均  {k:<7}: {sum(vs) / len(vs):.3f}  (min {min(vs):.2f} / max {max(vs):.2f})")

print()
print("=" * 96)
print("実験2③: 観測のみ + Jev（VLM 再実行あり）の confidence")
print("=" * 96)
for src in ["A_obs", "C_obs"]:
    f = Path(f"results/exp2/{src}_judged_jev.json")
    if not f.exists():
        continue
    j = json.loads(f.read_text())
    confs = [m["confidence"] for m in j["detail"] if m.get("confidence") is not None]
    print(f"  {src}: 判定={ {k: v['verdict'] for k, v in j['results'].items()} }")
    print(f"       confidence 平均 {sum(confs) / len(confs):.3f}  min {min(confs):.2f}  max {max(confs):.2f}")
