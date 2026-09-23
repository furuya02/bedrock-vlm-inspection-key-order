"""検査対象9枚を、ラベル付きの一覧画像にする

本文では n1 や d1_stain といった ID で結果を示すので、
どれがどの画像かを最初に見せておくための図。

Usage:
    python scripts/make_contact_sheet.py --out ../Blog/001.png
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"

ROWS = [
    ("正常 5枚", [
        ("n1", "images/normal/n1.jpg"), ("n2", "images/normal/n2.jpg"),
        ("n3", "images/normal/n3.jpg"), ("n4", "images/normal/n4.jpg"),
        ("n5", "images/normal/n5.jpg"),
    ]),
    ("異常 4枚", [
        ("d1_stain", "images/defect/d1_stain.jpg"), ("d2_broken", "images/defect/d2_broken.jpg"),
        ("d3_deformed", "images/defect/d3_deformed.jpg"), ("d4_bent", "images/defect/d4_bent.jpg"),
    ]),
]
CAPTION = {"n1": "正常", "n2": "正常", "n3": "正常", "n4": "正常", "n5": "正常",
           "d1_stain": "汚れ", "d2_broken": "破損", "d3_deformed": "変形", "d4_bent": "曲がり"}

W, H = 380, 228          # タイル1枚の画像領域
PAD, LABEL_H, HEAD_H = 16, 58, 44
COLS = 5


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="../Blog/001.png")
    args = p.parse_args()

    f_id = ImageFont.truetype(FONT, 22)
    f_cap = ImageFont.truetype(FONT, 20)
    f_head = ImageFont.truetype(FONT, 26)

    tile_w, tile_h = W + PAD * 2, H + LABEL_H + PAD
    canvas_w = tile_w * COLS + PAD * 2
    canvas_h = PAD + sum(HEAD_H + tile_h for _ in ROWS) + PAD
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#ffffff")
    d = ImageDraw.Draw(canvas)

    y = PAD
    for head, items in ROWS:
        d.text((PAD + 4, y + 8), head, font=f_head, fill="#232F3E")
        y += HEAD_H
        for i, (name, path) in enumerate(items):
            x = PAD + i * tile_w
            im = Image.open(path)
            im.thumbnail((W, H))
            ox = x + PAD + (W - im.width) // 2
            oy = y + (H - im.height) // 2
            canvas.paste(im, (ox, oy))
            d.rectangle([x + PAD - 1, y - 1, x + PAD + W, y + H], outline="#c8ced3")
            color = "#232F3E" if name.startswith("n") else "#C62828"
            d.text((x + PAD, y + H + 10), name, font=f_id, fill=color)
            d.text((x + PAD, y + H + 34), CAPTION[name], font=f_cap, fill="#5A6C7D")
        y += tile_h

    out = Path(args.out)
    canvas.save(out)
    print(f"{out} を作成しました（{canvas.size[0]}x{canvas.size[1]}）")


if __name__ == "__main__":
    main()
