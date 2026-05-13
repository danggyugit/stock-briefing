"""경제 지표·실적 캘린더 수집 (Finnhub)."""
from __future__ import annotations

from datetime import date, timedelta

import requests

ECONOMIC_URL = "https://finnhub.io/api/v1/calendar/economic"
EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"


def fetch_economic_calendar(api_key: str, days_ahead: int = 7) -> list[dict]:
    """오늘~앞으로 N일 미국 주요 경제 지표 (impact=high). 실패 시 빈 리스트."""
    if not api_key:
        return []
    today = date.today()
    until = today + timedelta(days=days_ahead)
    try:
        r = requests.get(
            ECONOMIC_URL,
            params={"from": today.isoformat(), "to": until.isoformat(), "token": api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("economicCalendar", []) or []
    except Exception as e:
        print(f"[calendar] 경제 지표 실패: {e}")
        return []

    IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}
    out: list[dict] = []
    for e in data:
        if (e.get("country") or "").upper() != "US":
            continue
        impact = (e.get("impact") or "").lower()
        if impact not in IMPACT_RANK:
            continue
        out.append(
            {
                "time": e.get("time", ""),
                "event": e.get("event", ""),
                "impact": impact,
                "actual": e.get("actual"),
                "estimate": e.get("estimate"),
                "prev": e.get("prev"),
            }
        )
    # 중요도 우선, 같은 중요도면 시간 순
    out.sort(key=lambda x: (IMPACT_RANK.get(x["impact"], 9), x["time"]))
    return out


def fetch_earnings_calendar(api_key: str, days_ahead: int = 2, tickers: list[str] | None = None) -> dict:
    """실적 발표 캘린더 — yesterday(발표된 것, beat/miss 포함) + 이번 주 예정.
    tickers 필터 제공 시 해당 종목만. 실패 시 빈 dict.
    """
    if not api_key:
        return {"yesterday": [], "upcoming": []}
    today = date.today()
    past = today - timedelta(days=2)
    future = today + timedelta(days=days_ahead)
    try:
        r = requests.get(
            EARNINGS_URL,
            params={"from": past.isoformat(), "to": future.isoformat(), "token": api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("earningsCalendar", []) or []
    except Exception as e:
        print(f"[calendar] 실적 캘린더 실패: {e}")
        return {"yesterday": [], "upcoming": []}

    yesterday_key = (today - timedelta(days=1)).isoformat()
    ticker_filter = set(tickers or [])

    yesterday: list[dict] = []
    upcoming: list[dict] = []
    for e in data:
        sym = e.get("symbol", "")
        if ticker_filter and sym not in ticker_filter:
            continue
        row = {
            "symbol": sym,
            "date": e.get("date", ""),
            "hour": e.get("hour", ""),
            "eps_estimate": e.get("epsEstimate"),
            "eps_actual": e.get("epsActual"),
            "rev_estimate": e.get("revenueEstimate"),
            "rev_actual": e.get("revenueActual"),
        }
        if e.get("date") == yesterday_key and e.get("epsActual") is not None:
            yesterday.append(row)
        elif e.get("date", "") >= today.isoformat():
            upcoming.append(row)

    # 시총 대형주 위주로 우선 정렬 (심볼 짧은 순 간이 휴리스틱)
    yesterday.sort(key=lambda x: len(x["symbol"]))
    upcoming.sort(key=lambda x: (x["date"], len(x["symbol"])))
    return {"yesterday": yesterday[:8], "upcoming": upcoming[:8]}


if __name__ == "__main__":
    from config import FINNHUB_API_KEY, WATCHLIST
    econ = fetch_economic_calendar(FINNHUB_API_KEY, 7)
    print(f"경제 지표 {len(econ)}건")
    for e in econ[:5]:
        print(f"  {e['time']} [{e['impact']}] {e['event']}")
    earn = fetch_earnings_calendar(FINNHUB_API_KEY, 2, WATCHLIST)
    print(f"\n전일 발표 실적 {len(earn['yesterday'])}건")
    for e in earn["yesterday"]:
        print(f"  {e['symbol']}: EPS 예상 {e['eps_estimate']} vs 실제 {e['eps_actual']}")
    print(f"\n예정 실적 {len(earn['upcoming'])}건")
    for e in earn["upcoming"]:
        print(f"  {e['date']} {e['symbol']} ({e['hour']})")
