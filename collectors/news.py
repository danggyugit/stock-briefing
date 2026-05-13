"""뉴스 수집 — Finnhub 우선, 실패 시 Yahoo Finance RSS 폴백."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests


FINNHUB_GENERAL = "https://finnhub.io/api/v1/news"
FINNHUB_COMPANY = "https://finnhub.io/api/v1/company-news"
YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
YAHOO_MARKET_RSS = "https://finance.yahoo.com/news/rssindex"


def _finnhub_general(api_key: str, limit: int = 15) -> list[dict]:
    try:
        r = requests.get(FINNHUB_GENERAL, params={"category": "general", "token": api_key}, timeout=10)
        r.raise_for_status()
        items = r.json()[:limit]
        return [
            {
                "source": n.get("source", ""),
                "headline": n.get("headline", ""),
                "summary": n.get("summary", ""),
                "url": n.get("url", ""),
                "symbol": "",
                "datetime": int(n.get("datetime", 0)),
            }
            for n in items
        ]
    except Exception as e:
        print(f"[news] Finnhub general 실패: {e}")
        return []


def _finnhub_company(api_key: str, symbols: list[str], per_symbol: int = 2) -> list[dict]:
    out: list[dict] = []
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=2)
    for sym in symbols:
        try:
            r = requests.get(
                FINNHUB_COMPANY,
                params={"symbol": sym, "from": start.isoformat(), "to": today.isoformat(), "token": api_key},
                timeout=10,
            )
            r.raise_for_status()
            for n in r.json()[:per_symbol]:
                out.append(
                    {
                        "source": n.get("source", ""),
                        "headline": n.get("headline", ""),
                        "summary": n.get("summary", ""),
                        "url": n.get("url", ""),
                        "symbol": sym,
                        "datetime": int(n.get("datetime", 0)),
                    }
                )
        except Exception as e:
            print(f"[news] Finnhub {sym} 실패: {e}")
    return out


def _parse_rss_datetime(pub_date: str) -> int:
    try:
        return int(parsedate_to_datetime(pub_date).timestamp())
    except Exception:
        return 0


def _yahoo_rss(url: str, symbol: str = "", limit: int = 10) -> list[dict]:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:limit]
        return [
            {
                "source": "Yahoo Finance",
                "headline": (it.findtext("title") or "").strip(),
                "summary": (it.findtext("description") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "symbol": symbol,
                "datetime": _parse_rss_datetime(it.findtext("pubDate") or ""),
            }
            for it in items
        ]
    except Exception as e:
        print(f"[news] Yahoo RSS {symbol or 'market'} 실패: {e}")
        return []


def filter_news_since(news: dict, since_ts: int) -> dict:
    """since_ts(Unix timestamp) 이후 뉴스만 남김. datetime=0(미상)은 포함."""
    def _keep(n: dict) -> bool:
        ts = n.get("datetime", 0)
        return ts == 0 or ts >= since_ts

    return {key: [n for n in items if _keep(n)] for key, items in news.items()}


def filter_by_keywords(news_list: list[dict], keywords: list[str], limit: int = 5) -> list[dict]:
    """헤드라인·요약에서 키워드 매칭되는 뉴스만 추림. 중복 URL 제거."""
    pat = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    seen: set[str] = set()
    out: list[dict] = []
    for n in news_list:
        url = n.get("url", "")
        if url and url in seen:
            continue
        text = f"{n.get('headline','')} {n.get('summary','')}"
        if pat.search(text):
            out.append(n)
            if url:
                seen.add(url)
        if len(out) >= limit:
            break
    return out


def collect_news(finnhub_key: str, watchlist: list[str], extra_tickers: list[str] | None = None) -> dict:
    """뉴스 수집.
    extra_tickers: SP500 상위 이동 종목 등 watchlist 외 추가 조회 티커 (1건씩).
    """
    general: list[dict] = []
    company: list[dict] = []

    if finnhub_key:
        general = _finnhub_general(finnhub_key, limit=15)
        company = _finnhub_company(finnhub_key, watchlist, per_symbol=2)
        if extra_tickers:
            # watchlist와 중복 제거 후 조회
            unique_extras = [t for t in extra_tickers if t not in watchlist]
            company += _finnhub_company(finnhub_key, unique_extras, per_symbol=1)

    # 폴백 또는 보강
    if not general:
        general = _yahoo_rss(YAHOO_MARKET_RSS, limit=15)
    if not company:
        for sym in watchlist[:5]:
            company.extend(_yahoo_rss(YAHOO_RSS.format(symbol=sym), symbol=sym, limit=2))

    return {"general": general, "company": company}


if __name__ == "__main__":
    from config import FINNHUB_API_KEY, WATCHLIST
    data = collect_news(FINNHUB_API_KEY, WATCHLIST)
    print(f"일반 뉴스 {len(data['general'])}건, 종목 뉴스 {len(data['company'])}건")
    for n in data["general"][:3]:
        print(f"- [{n['source']}] {n['headline']}")
