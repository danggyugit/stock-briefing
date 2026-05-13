"""Gemini API로 시장·뉴스 데이터를 한국어 브리핑으로 요약."""
from __future__ import annotations

import re
import time

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from config import GEMINI_MODEL


SYSTEM_PROMPT = """당신은 한국의 30~40대 개인투자자를 위한 미국 증시 브리핑 작성자입니다.
아래 원자료(시세 + 뉴스)를 바탕으로 반드시 아래 순서·포맷으로 출력하세요.
지수·섹터·메모리·TrendForce·이벤트 섹션은 시스템이 별도 렌더링하므로 절대 포함 금지.

━━ 1단계: 관심 종목 (MU·SNDK) ━━

<b>👁 관심 종목</b>
• <b>MU</b> 마이크론 ±X.XX% — 현재 사업 상황, 관련 뉴스, 단기 catalyst/리스크 2~3줄
• <b>SNDK</b> 샌디스크 ±X.XX% — 동일 형식 2~3줄

━━ 2단계: 구분자 (필수, 절대 생략 금지) ━━

===BREAK===

━━ 3단계: 종목 설명 ([SP500 상승 TOP]·[SP500 하락 TOP] 전 종목) ━━

아래 형식으로 [SP500 상승 TOP]과 [SP500 하락 TOP]에 있는 종목을 빠짐없이 설명하라.
섹션 제목 없이 바로 시작. 추가 종목 금지. 누락 금지.

[티커] 1~2줄 설명 (왜 움직였는지 배경, 관련 뉴스 요지, 단기 catalyst 또는 리스크)
[티커] 1~2줄 설명
... (SP500 TOP 목록 종목 수만큼)

━━ 4단계: 핵심 뉴스 ━━

<b>📰 핵심 뉴스</b>
① 헤드라인 + 1~2줄 맥락 설명
② 헤드라인 + 1~2줄 맥락 설명
③ 헤드라인 + 1~2줄 맥락 설명
④ 헤드라인 + 1~2줄 맥락 설명
⑤ 헤드라인 + 1~2줄 맥락 설명
(정확히 5개 — 부족하면 섹터·매크로 동향으로 보완)

━━ 5단계: 관전 포인트 ━━

<b>💡 관전 포인트</b>
2~3줄. 환율·섹터 순환·실적 발표 등 구체 포인트 1~2개 + 전반 리스크 1줄

━━ 공통 원칙 ━━
- 👁 MU·SNDK는 이슈 없어도 필수 포함. 이슈 없으면 "조용한 흐름 — [상황 한 줄]".
- ===BREAK=== 는 반드시 단독 줄로 출력.
- 3단계 [TICKER] 형식: 대괄호 안에 티커만, 바로 뒤에 공백 하나 후 설명. 다른 형식 금지.
- 📰 각 뉴스: 헤드라인(누가/무엇을) + 1~2줄 맥락(왜 중요한지, 한국 투자자에 어떤 의미).
- HTML 태그는 <b></b>만 허용. 마크다운(* ** # --- 등), 다른 HTML 태그 절대 금지.
- 뉴스·설명에 '<' '>' '&' 문자 회피.
- 수치는 [원자료]에 있는 것만 사용. 근거 없는 수치·예측 금지.
"""


FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]


PROMPT_MIDDAY = """당신은 한국 시각 14시 기준 '점심 업데이트' 브리핑 작성자입니다.
오전 8시 풀 브리핑 이후 변화된 내용·신규 이슈 중심으로 간결하게 정리하세요.
지수·섹터·메모리·TrendForce 섹션은 시스템이 별도 렌더링하므로 포함 금지.

정확히 아래 3개 섹션만 작성:

<b>🔥 신규 종목 이슈</b>
• <b>티커</b> ±X.XX% — 오전 이후 새로 부각된 움직임·뉴스 1~2줄
... (4~6개 불릿, [필수 종목]은 변동이 눈에 띌 때만 포함)

<b>📰 미장 신규 뉴스</b>
① 한 줄 헤드라인 + 맥락 1줄 (점심시간 기준 fresh한 뉴스 위주)
② ...
③ ...
(3~5개)

<b>💡 오후 체크 포인트</b>
2줄로 오후 KOSPI 마감·유럽 개장·오늘 미장 예정 이벤트 중 주의할 것

원칙:
- 오전 브리핑과 중복되는 내용은 "여전히 유효" 정도로 한 줄만. 신규·변화에 집중.
- +3% 이상 🚀, -3% 이하 💥.
- HTML <b>만 허용. ** * # 등 금지.
"""


PROMPT_WEEKEND = """당신은 주말 글로벌 시장 뉴스 브리퍼입니다.
미국 증시는 주말에 휴장이므로 시세 데이터 없이 뉴스 중심으로 정리하세요.

정확히 아래 2개 섹션만 작성:

<b>📰 주말 주요 뉴스</b>
① 헤드라인 + 1~2줄 맥락 (다음 주 시장에 미칠 영향 포함)
② ...
③ ...
(5~7개. 지정학·경제·기술·반도체 분야 위주. 반도체·AI·메모리 관련 우선)

<b>💡 다음 주 체크포인트</b>
2~3줄. 다음 주 주요 일정·이벤트·리스크 요인 정리
(주요 경제지표 발표, 실적 시즌, 연준 발언, 지정학 이슈 등)

원칙:
- HTML <b>만 허용. 마크다운(* ** # 등) 절대 금지.
- 시세 수치는 제공되지 않으므로 근거 없는 수치·예측 사용 금지.
- 뉴스에 '<' '>' '&' 문자 회피.
"""


PROMPT_PREVIEW = """당신은 한국 시각 22시 기준 '미장 개장 프리뷰' 브리핑 작성자입니다.
미 증시 개장 1~2시간 전이므로 오늘 시장 대응 준비에 초점.
지수·섹터·이벤트·프리마켓 종목 섹션은 시스템이 별도 렌더링하므로 포함 금지.

정확히 아래 2개 섹션만 작성:

<b>📰 간밤 주요 뉴스</b>
① 헤드라인 + 오늘 미장에 미칠 영향 1줄
② ...
③ ...
(3~5개)

<b>💡 오늘 개장 체크포인트</b>
3줄로 작성:
- 오늘 주요 이벤트 (경제 지표 발표 시간, 실적 발표 종목)
- 주목할 섹터/테마 (프리마켓 움직임 참고)
- 리스크 요인

원칙:
- HTML <b>만 허용. 마크다운(* ** #)·다른 HTML 태그 금지.
- 뉴스는 한 줄 헤드라인 + 한 줄 맥락.
- 프리마켓 종목 움직임은 시스템이 이미 표시하므로 중복 생성 금지.
"""


def summarize(
    market_data: dict,
    news_data: dict,
    api_key: str,
    max_retries: int = 2,
    mode: str = "morning",
    sp500_movers: list[dict] | None = None,
) -> str:
    """기본 GEMINI_MODEL 사용. Quota 소진 시 폴백 모델 순차 시도.
    mode: morning | midday | preview — 프롬프트 분기
    sp500_movers: morning 전용. S&P 500 상위 이동 종목 목록.
    """
    genai.configure(api_key=api_key)
    if mode == "weekend":
        payload = _build_weekend_payload(news_data)
    else:
        payload = _build_payload(market_data, news_data, sp500_movers=sp500_movers)

    prompt_map = {
        "morning": SYSTEM_PROMPT,
        "midday": PROMPT_MIDDAY,
        "preview": PROMPT_PREVIEW,
        "weekend": PROMPT_WEEKEND,
    }
    selected_prompt = prompt_map.get(mode, SYSTEM_PROMPT)

    for model_name in [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]:
        model = genai.GenerativeModel(model_name, system_instruction=selected_prompt)
        for attempt in range(max_retries):
            try:
                response = model.generate_content(payload)
                text = (response.text or "").strip()
                if text:
                    if model_name != GEMINI_MODEL:
                        print(f"[summarizer] ⚠️ 폴백 모델 사용: {model_name}")
                    return _sanitize(text)
            except ResourceExhausted as e:
                err_str = str(e)
                is_daily = "PerDay" in err_str or "PerProjectPerModel-FreeTier" in err_str and "limit: 0" not in err_str
                if is_daily or attempt == max_retries - 1:
                    print(f"[summarizer] {model_name} 한도 소진 → 다음 모델로 폴백")
                    break  # 다음 모델로
                wait = _parse_retry_delay(err_str, default=60)
                print(f"[summarizer] {model_name} 레이트 리밋, {wait}초 대기 ({attempt+1}/{max_retries})")
                time.sleep(wait)

    raise RuntimeError("모든 Gemini 모델의 일일 한도가 소진됨")


def _parse_retry_delay(msg: str, default: int) -> int:
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
    return int(float(m.group(1))) + 2 if m else default


_ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre", "br"}


def _sanitize(text: str) -> str:
    """LLM이 실수로 섞은 마크다운·불허 HTML 태그를 Telegram HTML 안전 형식으로 변환."""
    # **bold** → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    # *italic* → <i>italic</i>
    text = re.sub(r"(?<!\w)\*([^\s*][^*]*[^\s*])\*(?!\w)", r"<i>\1</i>", text)
    # # 헤더 제거
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # <br> → 개행
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # <li>...</li> → "• ..." (불릿 포인트)
    text = re.sub(r"<li[^>]*>\s*", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*</li>", "", text, flags=re.IGNORECASE)
    # <ul>, </ul>, <ol>, </ol> 제거
    text = re.sub(r"</?(ul|ol)[^>]*>", "", text, flags=re.IGNORECASE)
    # 기타 불허 태그 제거 (허용된 태그는 유지)
    def _strip_tag(m):
        tag = m.group(1).lower()
        return m.group(0) if tag in _ALLOWED_TAGS else ""
    text = re.sub(r"</?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", _strip_tag, text)
    # 남은 단독 별표 제거
    text = text.replace("**", "").strip()
    # 중복 개행 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _build_weekend_payload(news: dict) -> str:
    """주말 전용 payload — 시세 없이 뉴스만."""
    lines = ["[주말 뉴스 — 미국 증시 휴장]", ""]
    lines += ["[일반 뉴스 헤드라인]"]
    for n in news["general"][:15]:
        lines.append(f"- ({n['source']}) {n['headline']}")
    if news.get("memory"):
        lines += ["", "[메모리/반도체 관련 뉴스]"]
        for n in news["memory"][:5]:
            lines.append(f"- ({n['source']}) {n['headline']}")
    if news.get("company"):
        lines += ["", "[종목 관련 뉴스]"]
        for n in news["company"][:10]:
            sym = f"[{n['symbol']}] " if n["symbol"] else ""
            lines.append(f"- {sym}{n['headline']}")
    return "\n".join(lines)


def _build_payload(market: dict, news: dict, sp500_movers: list[dict] | None = None) -> str:
    lines = ["[지수]", market["indices_text"], "", "[매크로]", market["macro_text"]]
    if market.get("spread_10y_3m") is not None:
        lines.append(f"[10Y-3M 스프레드] {market['spread_10y_3m']:+.2f}%p")
    if market.get("sectors_text"):
        lines += ["", "[섹터 ETF 등락률]", market["sectors_text"]]
    if market.get("fx_text"):
        lines += ["", "[환율/한국증시 — 참고용, 가볍게 언급]", market["fx_text"]]
    if market.get("memory_text"):
        lines += ["", "[메모리 시세]", market["memory_text"]]

    if market.get("essentials_text"):
        lines += ["", "[관심 종목 — MU·SNDK 반드시 커버]", market["essentials_text"]]

    # SP500 전체 스캔 결과 (morning 전용)
    if sp500_movers:
        gainers = [m for m in sp500_movers if m["change_pct"] > 0]
        losers  = [m for m in sp500_movers if m["change_pct"] <= 0]
        if gainers:
            lines += ["", "[SP500 상승 TOP]"]
            for m in gainers:
                lines.append(f"- {m['symbol']} ({m['name']}) {m['change_pct']:+.2f}% ${m['close']:.2f}")
        if losers:
            lines += ["", "[SP500 하락 TOP]"]
            for m in losers:
                lines.append(f"- {m['symbol']} ({m['name']}) {m['change_pct']:+.2f}% ${m['close']:.2f}")
    else:
        # SP500 스캔 실패 시 watchlist 등락으로 폴백
        lines += ["", "[상승 TOP (WATCHLIST)]", market["gainers_text"]]
        lines += ["", "[하락 TOP (WATCHLIST)]", market["losers_text"]]

    if news.get("memory"):
        lines += ["", "[메모리 뉴스 — DRAM/NAND/SSD 관련]"]
        for n in news["memory"][:5]:
            lines.append(f"- ({n['source']}) {n['headline']}")

    lines += ["", "[일반 뉴스 헤드라인]"]
    for n in news["general"][:12]:
        lines.append(f"- ({n['source']}) {n['headline']}")

    if news["company"]:
        lines += ["", "[종목 관련 뉴스]"]
        for n in news["company"][:20]:
            sym = f"[{n['symbol']}] " if n["symbol"] else ""
            lines.append(f"- {sym}{n['headline']}")

    return "\n".join(lines)


if __name__ == "__main__":
    from config import GEMINI_API_KEY, INDICES, MACRO, WATCHLIST, FINNHUB_API_KEY, require
    from collectors.market import collect_market
    from collectors.news import collect_news

    m = collect_market(INDICES, MACRO, WATCHLIST)
    n = collect_news(FINNHUB_API_KEY, WATCHLIST)
    print(summarize(m, n, require("GEMINI_API_KEY", GEMINI_API_KEY)))
