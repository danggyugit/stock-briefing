"""환경변수·설정 로드."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
# 여러 명에게 보내려면 콤마로 구분: "111,222,333"
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
FRED_API_KEY    = os.getenv("FRED_API_KEY", "").strip()

# 추적할 지수·매크로 티커 (Yahoo Finance 심볼)
INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
    "필라델피아 반도체(SOX)": "^SOX",
}

MACRO = {
    "10년물 국채금리": "^TNX",
    "달러인덱스(DXY)": "DX-Y.NYB",
    "WTI 원유": "CL=F",
    "금": "GC=F",
    "구리": "HG=F",
    "비트코인": "BTC-USD",
    "USD/JPY": "JPY=X",
}

# 장단기 금리차 (10Y-3M, Fed 선호 경기선행 지표)
YIELD_3M_SYMBOL = "^IRX"
YIELD_10Y_SYMBOL = "^TNX"

# 환율 · 한국 증시 (참고용)
FX_KR = {
    "USD/KRW": "KRW=X",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
}

# GICS 11개 섹터 ETF (미 증시 섹터별 자금 흐름)
SECTORS = {
    "기술(XLK)": "XLK",
    "통신(XLC)": "XLC",
    "경기소비(XLY)": "XLY",
    "금융(XLF)": "XLF",
    "산업(XLI)": "XLI",
    "헬스케어(XLV)": "XLV",
    "필수소비(XLP)": "XLP",
    "에너지(XLE)": "XLE",
    "유틸리티(XLU)": "XLU",
    "소재(XLB)": "XLB",
    "부동산(XLRE)": "XLRE",
}

# 차트용 종목 바스켓 (정규화 추이)
MEMORY_BASKET_CHART = [
    ("삼성전자", "005930.KS"),
    ("SK하이닉스", "000660.KS"),
    ("마이크론", "MU"),
    ("WDC", "WDC"),
]

# 대형 지수 3개월 추세 차트
TREND_CHART_SYMBOLS = [
    ("S&P 500", "^GSPC"),
]
TREND_PERIOD = "3mo"

# 선물 지수 (24시간 거래, preview 모드 전용 — 오버나이트 방향성 확인)
FUTURES = {
    "S&P 500 선물": "ES=F",
    "Nasdaq 선물": "NQ=F",
    "Dow 선물": "YM=F",
    "Russell 2000 선물": "RTY=F",
}

# 주요 종목 (섹터별 대표주 확장 — 33종목)
WATCHLIST = [
    # 빅테크 / AI
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # 반도체
    "AVGO", "AMD", "TSM", "MU", "SNDK", "QCOM", "INTC", "AMAT",
    # 금융
    "JPM", "BAC", "GS", "V", "MA",
    # 헬스케어
    "LLY", "UNH", "JNJ",
    # 에너지
    "XOM", "CVX",
    # 소비재 / 유통
    "WMT", "COST", "HD", "NKE",
    # 산업재 / 방산
    "CAT", "BA", "GE",
    # 미디어 / 스트리밍
    "NFLX",
]

# 움직임과 무관하게 매일 반드시 커버할 종목
ESSENTIAL_TICKERS = {
    "MU": "마이크론",
    "SNDK": "샌디스크",
}

# 매일 차트 이미지로 생성해 Telegram으로 함께 전송할 자산
CHART_SYMBOLS = [
    ("10년물 국채금리", "^TNX"),
    ("WTI 원유", "CL=F"),
]
CHART_PERIOD = "1mo"  # yfinance period: 1mo, 3mo, 6mo, 1y

# 💾 메모리 섹터 — 브리핑에 별도 표시할 메모리 관련 종목
MEMORY_TICKERS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "마이크론": "MU",
    "WDC": "WDC",
}

# 메모리 관련 뉴스 키워드 (DRAM·NAND·SSD 가격 트렌드 감지)
MEMORY_KEYWORDS = [
    "DRAM", "NAND", "SSD", "DDR5", "DDR4", "HBM",
    "memory price", "memory chip", "flash memory",
    "메모리", "하이닉스", "마이크론",
    "TrendForce", "DRAMeXchange",
]

GEMINI_MODEL = "gemini-2.5-flash"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def require(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"환경변수 {name} 가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return value
