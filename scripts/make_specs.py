"""実験2 用の spec を、idea036 の spec から機械的に作る

作るのは2種類。どちらも「何を変えたか」を最小にするのが目的なので、
手で書き直さずプログラムで変換し、差分をレポートに残す。

  ord … 出力スキーマの **キーの並び順だけ** を入れ替える（findings を verdict より前に）
        プロンプト本文は一文字も変えない。
        狙い: 「先に verdict を書かせていたこと」が検出低下の原因かを見る。

  obs … verdict / normal_observations / overall_notes をスキーマから外し、
        プロンプトの「■ 判定」節を削って「■ 出力」節を観測専用に差し替える。
        狙い: VLM に判断させず、観測だけを返させる。判断は後段（Jev / Haiku / ルール）が行う。
        ※ B / C の symmetry_check は「手順を踏んだ記録」＝観測なので残す。
        ※ B は「■ 出力」節に部位名・difference_from_normal・symmetry_check の指示が
          まとめて入っているため、節を差し替えずに残し、判定しない旨の一文だけ足す。

Usage:
    python scripts/make_specs.py
"""

import json
from collections import OrderedDict
from pathlib import Path

SRC = Path("results/idea036")
OUT = Path("specs")

# 観測のみ条件でスキーマから外すキー（判断と、判断の正当化にあたるもの）
DROP_FOR_OBS = ["verdict", "normal_observations", "overall_notes"]

OBS_OUTPUT_SECTION = """■ 出力
指定された JSON スキーマに従い、純粋な JSON のみを出力してください。
この工程では合否の判定を行いません。OK / REVIEW / NG といった判定は出力せず、見えたものの記述だけを返してください。
気になった箇所それぞれについて、欠陥種別、該当セル名（複数可）、確信度（0.0〜1.0）、根拠（見た目の具体的な記述）を記載してください。気になる箇所がない場合は findings を空配列にしてください。"""


def reorder_findings_first(schema):
    """properties と required で findings を verdict より前に出す。他は順序も中身も変えない"""
    props = schema["properties"]
    keys = list(props.keys())
    assert "verdict" in keys and "findings" in keys, keys
    keys.remove("findings")
    keys.insert(keys.index("verdict"), "findings")
    schema["properties"] = OrderedDict((k, props[k]) for k in keys)

    req = schema.get("required")
    if req and "verdict" in req and "findings" in req:
        req = [k for k in req if k != "findings"]
        req.insert(req.index("verdict"), "findings")
        schema["required"] = req
    return schema


def to_observation_only(schema):
    schema["properties"] = OrderedDict(
        (k, v) for k, v in schema["properties"].items() if k not in DROP_FOR_OBS
    )
    if "required" in schema:
        schema["required"] = [k for k in schema["required"] if k not in DROP_FOR_OBS]
    return schema


NO_JUDGEMENT = "この工程では合否の判定を行いません。OK / REVIEW / NG といった判定は出力せず、見えたものの記述だけを返してください。"


def strip_judgement(prompt, keep_output_body=False):
    """「■ 判定」節を削り、「■ 出力」節を観測専用にする

    keep_output_body=True のときは「■ 出力」節の本文を残し、判定しない旨の一文だけ足す（B 用）。
    """
    i, j = prompt.index("■ 判定"), prompt.index("■ 出力")
    assert i < j, "想定と違う並び"
    if keep_output_body:
        head, _, body = prompt[j:].partition("\n")
        return prompt[:i] + head + "\n" + NO_JUDGEMENT + "\n" + body
    tail = prompt[j:]
    # 「■ 出力」節の本体を差し替え、その後ろに続く補足（C の symmetry_check の指示など）は残す
    lines = tail.split("\n")
    body_end = next((n for n, l in enumerate(lines[1:], 1) if l.strip() == ""), len(lines))
    rest = "\n".join(lines[body_end:])
    return prompt[:i] + OBS_OUTPUT_SECTION + rest


def main():
    OUT.mkdir(exist_ok=True)
    report = []

    for tag, fname in [("A", "spec_clothespin_4x4.json"),
                       ("B", "spec_clothespin_partB.json"),
                       ("C", "spec_clothespin_partC.json")]:
        base = json.loads((SRC / fname).read_text(), object_pairs_hook=OrderedDict)
        # 参照画像のパスを本リポジトリのものに直す（内容は idea036 と同一の画像）
        base["_meta"]["normal_images"] = ["images/normal/n1.jpg", "images/normal/n5.jpg"]

        before = list(base["output_schema"]["properties"].keys())

        # ② 順序入替: スキーマのキー順だけ変える
        ord_spec = json.loads(json.dumps(base), object_pairs_hook=OrderedDict)
        ord_spec["output_schema"] = reorder_findings_first(ord_spec["output_schema"])
        ord_spec["_meta"]["variant"] = f"{tag}_ord_findings_first"
        (OUT / f"spec_{tag}_ord.json").write_text(json.dumps(ord_spec, ensure_ascii=False, indent=2))

        # ③ 観測のみ: 判断に関するキーとプロンプト節を落とす
        obs_spec = json.loads(json.dumps(base), object_pairs_hook=OrderedDict)
        obs_spec["output_schema"] = to_observation_only(obs_spec["output_schema"])
        obs_spec["inspection_prompt"] = strip_judgement(obs_spec["inspection_prompt"],
                                                        keep_output_body=(tag == "B"))
        obs_spec["_meta"]["variant"] = f"{tag}_obs_only"
        (OUT / f"spec_{tag}_obs.json").write_text(json.dumps(obs_spec, ensure_ascii=False, indent=2))

        report.append({
            "tag": tag,
            "keys_original": before,
            "keys_ord": list(ord_spec["output_schema"]["properties"].keys()),
            "keys_obs": list(obs_spec["output_schema"]["properties"].keys()),
            "prompt_same_as_original_ord": ord_spec["inspection_prompt"] == base["inspection_prompt"],
            "prompt_chars_original": len(base["inspection_prompt"]),
            "prompt_chars_obs": len(obs_spec["inspection_prompt"]),
        })

    (OUT / "make_specs_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for r in report:
        print(f"--- {r['tag']}")
        print(f"  元        : {r['keys_original']}")
        print(f"  ord       : {r['keys_ord']}")
        print(f"  obs       : {r['keys_obs']}")
        print(f"  ord のプロンプトは原文と同一か: {r['prompt_same_as_original_ord']}")
        print(f"  プロンプト文字数: {r['prompt_chars_original']} → obs {r['prompt_chars_obs']}")


if __name__ == "__main__":
    main()
