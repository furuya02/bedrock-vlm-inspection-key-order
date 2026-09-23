""".env をたどって環境変数に載せるだけの最小ローダ"""

import os
from pathlib import Path


def load_env():
    """カレントから上位に向かって .env を探し、未設定のキーだけ環境変数に入れる"""
    for d in [Path.cwd(), *Path.cwd().parents]:
        f = d / ".env"
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return f
    return None
