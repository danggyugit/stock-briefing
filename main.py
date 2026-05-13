"""미 증시 브리핑 파이프라인.

실행:
  python main.py                    # morning (기본)
  python main.py --mode midday      # 점심 업데이트
  python main.py --mode preview     # 미장 개장 프리뷰
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

# Windows 콘솔이 cp949인 경우 이모지 출력 실패 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from charts import make_basket_chart, make_charts, make_sector_heatmap, make_spot_history_chart
from collectors.calendar import fetch_earnings_calendar, fetch_economic_calendar
from collectors.market import collect_market, collect_sp500_movers
from collectors.memory_prices import (
    append_spot_history,
    fetch_dram_spot_prices,
    fetch_trendforce_memory_news,
    load_spot_history,
)
from collectors.news import collect_news, filter_by_keywords, filter_news_since
from collectors.sentiment import fetch_fear_greed
from formatter import compose_brief, compose_midday, compose_preview, compose_weekend
from collectors.fred import fetch_fred_indicators
from config import (
    CHART_PERIOD,
    CHART_SYMBOLS,
    ESSENTIAL_TICKERS,
    FINNHUB_API_KEY,
    FRED_API_KEY,
    FUTURES,
    FX_KR,
    GEMINI_API_KEY,
    INDICES,
    LOG_DIR,
    MACRO,
    MEMORY_BASKET_CHART,
    MEMORY_KEYWORDS,
    MEMORY_TICKERS,
    SECTORS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_IDS,
    WATCHLIST,
    YIELD_3M_SYMBOL,
    YIELD_10Y_SYMBOL,
    require,
)
from notifier import send_telegram, send_telegram_photo
from summarizer import summarize


def _is_weekend() -> bool:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Seoul")).weekday() >= 5  # 5=토, 6=일


def build_weekend_brief() -> tuple[str, dict]:
    """주말 전용 브리핑 — 뉴스·이슈만, 시세 데이터 없음."""
    news = collect_news(FINNHUB_API_KEY, WATCHLIST)
    news["memory"] = filter_by_keywords(news["general"] + news["company"], MEMORY_KEYWORDS, limit=5)
    fng = fetch_fear_greed()
    trendforce_news = fetch_trendforce_memory_news(limit=3)

    narrative = summarize({}, news, require("GEMINI_API_KEY", GEMINI_API_KEY), mode="weekend")
    text = compose_weekend(narrative, fng=fng, trendforce_news=trendforce_news)
    return text, {}


def build_brief(mode: str = "morning") -> tuple[str, dict]:
    """브리핑 텍스트와 원자료(차트 생성에 재사용) 리턴.
    mode: morning (08:00) | midday (14:00) | preview (22:00)
    """
    market = collect_market(
        INDICES, MACRO, WATCHLIST, ESSENTIAL_TICKERS, MEMORY_TICKERS,
        fx_kr=FX_KR, sectors=SECTORS,
        yield_3m=YIELD_3M_SYMBOL, yield_10y=YIELD_10Y_SYMBOL,
    )

    fng = fetch_fear_greed()

    # 모드별 데이터 수집 범위 최적화
    if mode == "morning":
        # S&P 500 전체 스캔 (30~60초 소요)
        sp500_movers = collect_sp500_movers(top_n=10)
        mover_syms = [m["symbol"] for m in sp500_movers]

        news = collect_news(FINNHUB_API_KEY, WATCHLIST, extra_tickers=mover_syms)
        news["memory"] = filter_by_keywords(news["general"] + news["company"], MEMORY_KEYWORDS, limit=5)

        econ = fetch_economic_calendar(FINNHUB_API_KEY, days_ahead=7)
        earn = fetch_earnings_calendar(FINNHUB_API_KEY, days_ahead=2, tickers=WATCHLIST)
        dram_spot = fetch_dram_spot_prices()
        append_spot_history(dram_spot, LOG_DIR / "spot_history.csv")
        trendforce_news = fetch_trendforce_memory_news(limit=3)
        fred = fetch_fred_indicators(FRED_API_KEY)

        narrative = summarize(market, news, require("GEMINI_API_KEY", GEMINI_API_KEY), mode="morning", sp500_movers=sp500_movers)
        text = compose_brief(
            market, narrative=narrative,
            economic=econ, upcoming_earnings=earn["upcoming"],
            yesterday_earnings=earn["yesterday"], fng=fng,
            dram_spot=dram_spot, trendforce_news=trendforce_news,
            sp500_movers=sp500_movers,
            fred_indicators=fred,
        )

    elif mode == "midday":
        news = collect_news(FINNHUB_API_KEY, WATCHLIST)
        # 오늘 08:00 KST 이후 뉴스만 LLM에 전달 (아침 브리핑 이후 신규 뉴스만)
        from zoneinfo import ZoneInfo as _ZI
        _kst = _ZI("Asia/Seoul")
        _since = int(datetime.now(_kst).replace(hour=8, minute=0, second=0, microsecond=0).timestamp())
        news = filter_news_since(news, _since)
        news["memory"] = filter_by_keywords(news["general"] + news["company"], MEMORY_KEYWORDS, limit=5)
        trendforce_news = fetch_trendforce_memory_news(limit=3)
        from collectors.market import fetch_quote
        from dataclasses import asdict
        futures_quotes = [asdict(q) for name, sym in FUTURES.items() if (q := fetch_quote(name, sym))]
        narrative = summarize(market, news, require("GEMINI_API_KEY", GEMINI_API_KEY), mode="midday")
        text = compose_midday(
            market, narrative=narrative, fng=fng,
            trendforce_news=trendforce_news, futures_quotes=futures_quotes,
        )

    elif mode == "preview":
        news = collect_news(FINNHUB_API_KEY, WATCHLIST)
        news["memory"] = filter_by_keywords(news["general"] + news["company"], MEMORY_KEYWORDS, limit=5)
        earn = fetch_earnings_calendar(FINNHUB_API_KEY, days_ahead=1, tickers=WATCHLIST)
        today_str = date.today().isoformat()
        today_earnings = [e for e in earn.get("upcoming", []) if e.get("date") == today_str]
        # 선물 지수 시세 (24시간 거래, 진짜 오버나이트 방향성)
        from collectors.market import collect_extended_movers, fetch_quote
        from dataclasses import asdict
        futures_quotes = [asdict(q) for name, sym in FUTURES.items() if (q := fetch_quote(name, sym))]
        # 프리/애프터마켓 움직임 — watchlist + essential 전종목 스캔, 움직임 큰 순 상위 8개
        premarket_movers = collect_extended_movers(WATCHLIST, top_n=8)
        narrative = summarize(market, news, require("GEMINI_API_KEY", GEMINI_API_KEY), mode="preview")
        text = compose_preview(
            market, narrative=narrative,
            today_earnings=today_earnings, fng=fng,
            futures_quotes=futures_quotes,
            premarket_movers=premarket_movers,
        )

    else:
        raise ValueError(f"알 수 없는 mode: {mode}")

    return text, market


def save_log(text: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"brief_{ts}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _build_all_charts(market: dict, mode: str = "morning") -> list[tuple[str, Path]]:
    """모드별 차트 세트. midday/preview는 stale 데이터 지양 → 차트 없음."""
    charts: list[tuple[str, Path]] = []

    if mode == "morning":
        # 풀 차트 세트 (미 증시 마감 직후라 모든 데이터 신선)
        charts = make_charts(CHART_SYMBOLS, LOG_DIR, CHART_PERIOD)

        p = make_sector_heatmap(market.get("sectors", []), LOG_DIR)
        if p:
            charts.append(("🏭 미 증시 섹터 등락률", p))

        p = make_basket_chart(MEMORY_BASKET_CHART, "메모리 주가 추이", LOG_DIR, period="3mo")
        if p:
            charts.append(("💾 메모리 바스켓 (시작일 100 기준)", p))

        history = load_spot_history(LOG_DIR / "spot_history.csv")
        # 절대가격 차트
        p = make_spot_history_chart(history, LOG_DIR, min_points=2, normalized=False)
        if p:
            charts.append(("💰 DRAM/NAND 스팟 현물가 (절대가)", p))
        # 정규화 차트 (시작일=100, 변동률 한눈에 비교)
        p = make_spot_history_chart(history, LOG_DIR, min_points=2, normalized=True)
        if p:
            charts.append(("📊 DRAM/NAND 스팟 정규화 추이 (시작일=100)", p))

    return charts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["morning", "midday", "preview"], default="morning")
    args = parser.parse_args()
    mode = args.mode

    try:
        if _is_weekend():
            if mode != "morning":
                print(f"[skip] 주말 {mode} 브리핑 — 토·일은 아침 요약만 발송")
                return 0
            brief, market = build_weekend_brief()
        else:
            brief, market = build_brief(mode)

        log_path = save_log(brief)
        print(f"[ok] 브리핑 생성 완료 → {log_path}")
        print("-" * 40)
        print(brief)
        print("-" * 40)

        token = require("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
        if not TELEGRAM_CHAT_IDS:
            raise RuntimeError("TELEGRAM_CHAT_ID 환경변수가 비어 있습니다. .env를 확인하세요.")

        charts = [] if _is_weekend() else _build_all_charts(market, mode)

        import time as _time
        for chat in TELEGRAM_CHAT_IDS:
            try:
                send_telegram(token, chat, brief)
                _time.sleep(1.5)  # 플러드 제한 회피
                for caption, path in charts:
                    send_telegram_photo(token, chat, path, caption=caption)
                    _time.sleep(1.5)
                print(f"[ok] {chat} 전송 완료 (텍스트 + 차트 {len(charts)}장)")
            except Exception as e:
                print(f"[fail] {chat} 전송 실패: {e}", file=sys.stderr)

        return 0
    except Exception as e:
        err = f"[stock_briefing 오류] {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        print(err, file=sys.stderr)
        save_log(err)
        try:
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS:
                # 장애 알림은 첫 번째 chat_id(관리자)에게만
                send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS[0], f"⚠️ stock_briefing 실패\n{type(e).__name__}: {e}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
