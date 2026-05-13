"""CNN Fear & Greed Index 수집."""
from __future__ import annotations

import requests

FNG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def fetch_fear_greed() -> dict | None:
    """CNN F&G 최신 수치. 실패 시 None."""
    try:
        r = requests.get(
            FNG_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.cnn.com/markets/fear-and-greed",
                "Accept": "application/json",
            },
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        cur = d.get("fear_and_greed", {})
        score = cur.get("score")
        rating = (cur.get("rating") or "").lower()
        if score is None:
            return None
        label_map = {
            "extreme fear": "극도의 공포",
            "fear": "공포",
            "neutral": "중립",
            "greed": "탐욕",
            "extreme greed": "극도의 탐욕",
        }
        return {
            "score": round(float(score)),
            "rating_en": rating,
            "rating_kr": label_map.get(rating, rating),
            "previous_close": cur.get("previous_close"),
            "previous_1_week": cur.get("previous_1_week"),
            "previous_1_month": cur.get("previous_1_month"),
        }
    except Exception as e:
        print(f"[sentiment] Fear & Greed 실패: {e}")
        return None


if __name__ == "__main__":
    fg = fetch_fear_greed()
    print(fg)
