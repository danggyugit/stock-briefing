"""yfinance 기반 지수·매크로·종목 시세 수집."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import yfinance as yf


@dataclass
class Quote:
    name: str
    symbol: str
    close: float
    change_pct: float

    def line(self) -> str:
        arrow = "🔺" if self.change_pct > 0 else ("🔻" if self.change_pct < 0 else "➖")
        return f"{arrow} {self.name}: {self.close:,.2f} ({self.change_pct:+.2f}%)"


def fetch_quote(name: str, symbol: str) -> Quote | None:
    """전일 종가와 전전일 대비 변동률 계산. 실패 시 None."""
    try:
        hist = yf.Ticker(symbol).history(period="5d", auto_adjust=False)
        if len(hist) < 2:
            return None
        close = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        change = (close - prev) / prev * 100
        return Quote(name=name, symbol=symbol, close=close, change_pct=change)
    except Exception as e:
        print(f"[market] {symbol} 실패: {e}")
        return None


def fetch_extended_quote(symbol: str) -> dict | None:
    """프리마켓·애프터마켓 시세 조회.
    preMarketPrice 우선, 없으면 postMarketPrice 폴백.
    source: pre | post | None
    """
    try:
        info = yf.Ticker(symbol).fast_info
        # fast_info는 빠르지만 pre/post 정보 제한적 → info 폴백
        pre_price = None
        pre_pct = None
        post_price = None
        post_pct = None
        try:
            full = yf.Ticker(symbol).info
            pre_price = full.get("preMarketPrice")
            pre_pct = full.get("preMarketChangePercent")
            post_price = full.get("postMarketPrice")
            post_pct = full.get("postMarketChangePercent")
        except Exception:
            pass

        if pre_price is not None and pre_pct is not None:
            return {"symbol": symbol, "price": float(pre_price), "change_pct": float(pre_pct), "source": "프리"}
        if post_price is not None and post_pct is not None:
            return {"symbol": symbol, "price": float(post_price), "change_pct": float(post_pct), "source": "애프터"}
        return None
    except Exception as e:
        print(f"[market] {symbol} 확장시세 실패: {e}")
        return None


def collect_extended_movers(symbols: list[str], top_n: int = 8) -> list[dict]:
    """여러 종목의 프리/애프터마켓 시세를 모아 움직임 큰 순으로 top_n 반환."""
    quotes = []
    for sym in symbols:
        q = fetch_extended_quote(sym)
        if q is not None:
            quotes.append(q)
    quotes.sort(key=lambda q: abs(q["change_pct"]), reverse=True)
    return quotes[:top_n]


def collect_market(
    indices: dict[str, str],
    macro: dict[str, str],
    watchlist: list[str],
    essentials: dict[str, str] | None = None,
    memory: dict[str, str] | None = None,
    fx_kr: dict[str, str] | None = None,
    sectors: dict[str, str] | None = None,
    yield_3m: str | None = None,
    yield_10y: str | None = None,
) -> dict:
    idx = [q for n, s in indices.items() if (q := fetch_quote(n, s))]
    mac = [q for n, s in macro.items() if (q := fetch_quote(n, s))]
    stk = [q for s in watchlist if (q := fetch_quote(s, s))]

    stk_sorted = sorted(stk, key=lambda q: q.change_pct, reverse=True)
    top_gainers = stk_sorted[:5]
    top_losers = sorted(stk_sorted[-5:], key=lambda q: q.change_pct)

    ess_quotes: list[Quote] = []
    if essentials:
        by_sym = {q.symbol: q for q in stk}
        for sym, kname in essentials.items():
            q = by_sym.get(sym) or fetch_quote(sym, sym)
            if q:
                ess_quotes.append(Quote(name=f"{kname}({sym})", symbol=sym, close=q.close, change_pct=q.change_pct))

    mem_quotes: list[Quote] = []
    if memory:
        for kname, sym in memory.items():
            q = fetch_quote(f"{kname}({sym})", sym)
            if q:
                mem_quotes.append(q)

    fx_quotes: list[Quote] = []
    if fx_kr:
        for kname, sym in fx_kr.items():
            q = fetch_quote(kname, sym)
            if q:
                fx_quotes.append(q)

    sector_quotes: list[Quote] = []
    if sectors:
        for kname, sym in sectors.items():
            q = fetch_quote(kname, sym)
            if q:
                sector_quotes.append(q)
        sector_quotes.sort(key=lambda q: q.change_pct, reverse=True)

    spread_10y_3m: float | None = None
    if yield_3m and yield_10y:
        q3 = fetch_quote("3M", yield_3m)
        q10 = fetch_quote("10Y", yield_10y)
        if q3 and q10:
            spread_10y_3m = q10.close - q3.close

    return {
        "indices": [asdict(q) for q in idx],
        "macro": [asdict(q) for q in mac],
        "gainers": [asdict(q) for q in top_gainers],
        "losers": [asdict(q) for q in top_losers],
        "essentials": [asdict(q) for q in ess_quotes],
        "memory": [asdict(q) for q in mem_quotes],
        "fx": [asdict(q) for q in fx_quotes],
        "sectors": [asdict(q) for q in sector_quotes],
        "spread_10y_3m": spread_10y_3m,
        "indices_text": "\n".join(q.line() for q in idx),
        "macro_text": "\n".join(q.line() for q in mac),
        "gainers_text": "\n".join(q.line() for q in top_gainers),
        "losers_text": "\n".join(q.line() for q in top_losers),
        "essentials_text": "\n".join(q.line() for q in ess_quotes),
        "memory_text": "\n".join(q.line() for q in mem_quotes),
        "fx_text": "\n".join(q.line() for q in fx_quotes),
        "sectors_text": "\n".join(q.line() for q in sector_quotes),
    }


_SP500_ESSENTIAL_EXCLUDE = {"MU", "SNDK"}  # 관심 종목 섹션에서 별도 처리


def collect_sp500_movers(top_n: int = 10) -> list[dict]:
    """S&P 500 전체 배치 스캔 → 등락 상위 top_n개 (상승·하락 각 절반) 반환.
    MU·SNDK는 관심 종목 섹션에서 따로 다루므로 결과에서 제외.
    """
    try:
        import pandas as pd
        print("[market] S&P 500 목록 로드 중 (Wikipedia)...")
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        sp500_df = tables[0]
        all_tickers = sp500_df["Symbol"].str.replace(".", "-", regex=False).tolist()
        name_map = dict(zip(
            sp500_df["Symbol"].str.replace(".", "-", regex=False),
            sp500_df["Security"],
        ))

        print(f"[market] yfinance 배치 다운로드 ({len(all_tickers)}종목) — 30~60초 소요...")
        raw = yf.download(all_tickers, period="5d", progress=False, threads=True, auto_adjust=False)
        closes = raw["Close"].dropna(how="all")
        if len(closes) < 2:
            print("[market] S&P 500 데이터 부족 (2일치 미만)")
            return []

        prev = closes.iloc[-2]
        last = closes.iloc[-1]
        pct = ((last - prev) / prev * 100).dropna()

        half = max(1, top_n // 2)
        gainers = pct.nlargest(half)
        losers = pct.nsmallest(half)

        result: list[dict] = []
        for sym, chg in list(gainers.items()) + list(losers.items()):
            if sym in _SP500_ESSENTIAL_EXCLUDE:
                continue
            result.append({
                "symbol": sym,
                "name": name_map.get(sym, sym),
                "change_pct": round(float(chg), 2),
                "close": round(float(last[sym]), 2),
            })
        print(f"[market] S&P 500 스캔 완료 — 상승 {half}개 / 하락 {half}개 추출")
        return result
    except Exception as e:
        print(f"[market] S&P 500 스캔 실패: {e}")
        return []


if __name__ == "__main__":
    from config import INDICES, MACRO, WATCHLIST, ESSENTIAL_TICKERS, MEMORY_TICKERS
    data = collect_market(INDICES, MACRO, WATCHLIST, ESSENTIAL_TICKERS, MEMORY_TICKERS)
    print("=== 지수 ===\n" + data["indices_text"])
    print("\n=== 매크로 ===\n" + data["macro_text"])
    print("\n=== 상승 TOP ===\n" + data["gainers_text"])
    print("\n=== 하락 TOP ===\n" + data["losers_text"])
    print("\n=== 필수 종목 ===\n" + data["essentials_text"])
    print("\n=== 메모리 섹터 ===\n" + data["memory_text"])
