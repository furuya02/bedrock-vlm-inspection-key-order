"""Jev（TypeSafe AI の System One モデル）を Vercel AI Gateway 経由で叩く

経路は2系統ある。同じモデルなのに返るフィールド名が違うので、両方用意して比較できるようにした。

  A: TypeSafe 互換 API  /typesafe/v1/systemone
     本家 api.typesafe.ai と同形。型名は noul / choice / score。
     本命はこちら（本家 early access が通った人がそのまま使えるコードになる）。

  B: Gateway 独自 API   /v1/evaluate
     型名が boolean になり、noul の代わりに probability が返る。usage も camelCase。

Docs:
  https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe
  https://vercel.com/docs/ai-gateway/modalities/evaluation
  https://docs.typesafe.ai/api
"""

import os
import time

import requests

from _env import load_env

GATEWAY = "https://ai-gateway.vercel.sh"
MODEL = "typesafe-ai/jev"


def _key():
    load_env()
    k = os.environ.get("AI_GATEWAY_API_KEY")
    if not k:
        raise SystemExit("AI_GATEWAY_API_KEY が無い。idea038/.env に置いてください")
    return k


# 連投すると Gateway 側が 429 / 503 を返す。公式ドキュメントが
# 「429 / 529 は指数バックオフでリトライ」と指示しているのでそれに従う。
# 実測では 9 枚 x 3 run を素で投げた時点で 429 と 503 の両方が出た。
_RETRY_STATUS = {429, 500, 502, 503, 529}
_MAX_RETRY = 6

# リトライで何が起きたかを呼び出し側から見えるようにしておく（記事に書くため）
retry_log = []


def _post(path, body):
    url = f"{GATEWAY}{path}"
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}

    wait = 1.0
    for attempt in range(_MAX_RETRY):
        t = time.perf_counter()
        r = requests.post(url, headers=headers, json=body, timeout=60)
        elapsed = time.perf_counter() - t

        if r.status_code not in _RETRY_STATUS:
            return r, elapsed

        retry_log.append({"status": r.status_code, "attempt": attempt + 1, "wait": wait})
        print(f"    retry: HTTP {r.status_code} ({attempt + 1}回目) {wait:.0f}秒待つ", flush=True)
        # Retry-After が返っていればそれに従う
        after = r.headers.get("Retry-After")
        time.sleep(float(after) if after and after.isdigit() else wait)
        wait = min(wait * 2, 30.0)

    return r, elapsed


def system_one(state, questions, model=MODEL):
    """A: TypeSafe 互換 API。noul / choice / score がそのまま返る"""
    r, elapsed = _post("/typesafe/v1/systemone", {"model": model, "state": state, "questions": questions})
    r.raise_for_status()
    return r.json(), elapsed


def evaluate(state, questions, model=MODEL):
    """B: Gateway 独自 API。noul ではなく boolean / probability になる"""
    r, elapsed = _post("/v1/evaluate", {"model": model, "state": state, "questions": questions})
    r.raise_for_status()
    return r.json(), elapsed


def choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul(instructions):
    return {"type": "noul", "instructions": instructions}


def score(instructions, criteria):
    return {"type": "score", "instructions": instructions, "criteria": criteria}


def cost_of(res):
    """provider_metadata から1リクエストの実費を取り出す（無ければ None）"""
    md = res.get("provider_metadata") or res.get("providerMetadata") or {}
    return (md.get("gateway") or {}).get("cost")
