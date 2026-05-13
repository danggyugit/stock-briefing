"""FRED API (Federal Reserve Economic Data) 주요 경제 지표 수집.
무료 API 키: https://fred.stlouisfed.org/docs/api/api_key.html
"""
from __future__ import annotations

from datetime import date
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_obs(series_id: str, api_key: str, limit: int = 14) -> list[dict]:
    """FRED 시계열 최신 N개 관측값 (최신순, 결측치 제외)."""
    try:
        r = requests.get(
            FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "sort_order": "desc",
                "limit": limit,
                "file_type": "json",
            },
            timeout=10,
        )
        r.raise_for_status()
        return [o for o in r.json().get("observations", []) if o["value"] not in (".", "")]
    except Exception as e:
        print(f"[fred] {series_id} 실패: {e}")
        return []


def _is_recent(date_str: str, days: int = 14) -> bool:
    try:
        return (date.today() - date.fromisoformat(date_str)).days <= days
    except Exception:
        return False


def _yoy(obs: list[dict]) -> float | None:
    """13번째 이전 관측값 대비 YoY% 변화."""
    if len(obs) < 13:
        return None
    latest, yr_ago = float(obs[0]["value"]), float(obs[12]["value"])
    return (latest - yr_ago) / abs(yr_ago) * 100 if yr_ago else None


def _mom(obs: list[dict]) -> float | None:
    """직전 관측값 대비 변화량."""
    if len(obs) < 2:
        return None
    return float(obs[0]["value"]) - float(obs[1]["value"])


def fetch_fred_indicators(api_key: str) -> dict:
    """주요 FRED 경제 지표 수집. 아침 브리핑 전용."""
    if not api_key:
        return {}
    out: dict = {}

    # ── 물가 ──────────────────────────────────────────────────────────────
    obs = _fetch_obs("CPIAUCSL", api_key, 14)
    if obs:
        out["cpi"] = {
            "yoy": _yoy(obs),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    obs = _fetch_obs("PCEPILFE", api_key, 14)
    if obs:
        out["core_pce"] = {
            "yoy": _yoy(obs),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    # ── 고용 ──────────────────────────────────────────────────────────────
    obs = _fetch_obs("UNRATE", api_key, 3)
    if obs:
        out["unrate"] = {
            "value": float(obs[0]["value"]),
            "mom": _mom(obs),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    obs = _fetch_obs("PAYEMS", api_key, 3)
    if obs:
        out["nfp"] = {
            "mom": _mom(obs),  # 전월 대비 증감 (단위: 천 명)
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    # ── 통화/유동성 ────────────────────────────────────────────────────────
    obs = _fetch_obs("FEDFUNDS", api_key, 2)
    if obs:
        out["fedfunds"] = {
            "value": float(obs[0]["value"]),
            "date": obs[0]["date"],
        }

    obs = _fetch_obs("M2SL", api_key, 14)
    if obs:
        out["m2"] = {
            "value": float(obs[0]["value"]) / 1000,  # 십억 → 조 달러
            "yoy": _yoy(obs),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    obs = _fetch_obs("WALCL", api_key, 3)
    if obs:
        out["fed_assets"] = {
            "value": float(obs[0]["value"]) / 1_000_000,  # 백만 → 조 달러
            "mom": (_mom(obs) or 0) / 1_000_000,
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"], days=10),
        }

    # ── 금리 (2Y·10Y FRED → 10Y-2Y 스프레드) ─────────────────────────────
    obs = _fetch_obs("DGS2", api_key, 3)
    if obs:
        out["dgs2"] = {
            "value": float(obs[0]["value"]),
            "change": _mom(obs),
            "date": obs[0]["date"],
        }

    obs = _fetch_obs("DGS10", api_key, 3)
    if obs:
        out["dgs10"] = {
            "value": float(obs[0]["value"]),
            "change": _mom(obs),
            "date": obs[0]["date"],
        }

    if "dgs2" in out and "dgs10" in out:
        out["spread_10y_2y"] = out["dgs10"]["value"] - out["dgs2"]["value"]

    # ── 신용 위험 ──────────────────────────────────────────────────────────
    # BofA HY OAS Spread — 주식시장 위험선호도 바로미터 (높을수록 공포)
    obs = _fetch_obs("BAMLH0A0HYM2", api_key, 3)
    if obs:
        out["hy_spread"] = {
            "value": float(obs[0]["value"]),
            "change": _mom(obs),
            "date": obs[0]["date"],
            "is_recent": True,  # 일별 데이터
        }

    # ── 경기 동향 ──────────────────────────────────────────────────────────
    # Chicago Fed National Activity Index: >0 평균 이상, <-0.70 침체 위험
    obs = _fetch_obs("CFNAI", api_key, 2)
    if obs:
        out["cfnai"] = {
            "value": float(obs[0]["value"]),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    # ── 소비 심리 ──────────────────────────────────────────────────────────
    obs = _fetch_obs("UMCSENT", api_key, 3)
    if obs:
        out["michigan"] = {
            "value": float(obs[0]["value"]),
            "mom": _mom(obs),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    # 소매판매 MoM% (계절 조정, 식품서비스 제외)
    obs = _fetch_obs("RSXFS", api_key, 3)
    if obs and len(obs) >= 2:
        cur, prev = float(obs[0]["value"]), float(obs[1]["value"])
        mom_pct = (cur - prev) / prev * 100 if prev else None
        out["retail_sales"] = {
            "mom_pct": mom_pct,
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    # ── 침체 경보 ──────────────────────────────────────────────────────────
    # Sahm Rule: 0.50 초과 시 침체 신호 (현재 실업률 상승 속도 측정)
    obs = _fetch_obs("SAHMCURRENT", api_key, 2)
    if obs:
        out["sahm"] = {
            "value": float(obs[0]["value"]),
            "date": obs[0]["date"],
            "is_recent": _is_recent(obs[0]["date"]),
        }

    return out


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("FRED_API_KEY", "")
    data = fetch_fred_indicators(key)
    for k, v in data.items():
        print(f"{k}: {v}")
