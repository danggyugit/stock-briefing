"""시세 데이터를 카드형 텔레그램 HTML 브리핑으로 직접 렌더링.

지수·매크로·메모리 섹션은 이 모듈이 담당 (LLM 우회 → 환각 방지).
LLM은 🔥 종목 이슈·📰 핵심 뉴스·💡 관전 포인트만 생성.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as h
from zoneinfo import ZoneInfo

SEP = "━━━━━━━━━━━━━━━━━"


def _arrow(pct: float) -> str:
    if pct > 0.1:
        return "🔺"
    if pct < -0.1:
        return "🔻"
    return "➖"


def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _fmt_value(symbol: str, close: float) -> str:
    if symbol == "^TNX":
        return f"{close:.2f}%"
    if symbol == "CL=F":
        return f"${close:.2f}"
    if symbol == "GC=F":
        return f"${close:,.0f}"
    if symbol == "BTC-USD":
        return f"${close:,.0f}"
    if symbol == "DX-Y.NYB":
        return f"{close:.2f}"
    if symbol == "HG=F":
        return f"${close:.2f}/lb"
    if symbol == "JPY=X":
        return f"¥{close:.2f}"
    return f"{close:,.2f}"


MODE_TITLES = {
    "morning": "美 증시 마감 브리핑",
    "midday": "점심 뉴스 업데이트",
    "preview": "미장 개장 프리뷰",
    "weekend": "주말 뉴스 브리핑",
}


def header(mode: str = "morning") -> str:
    kst = datetime.now(ZoneInfo("Asia/Seoul"))
    dow = "월화수목금토일"[kst.weekday()]
    title = MODE_TITLES.get(mode, "美 증시 브리핑")
    emoji = {"morning": "🌅", "midday": "🍱", "preview": "🌙", "weekend": "🗓"}.get(mode, "🇺🇸")
    return (
        f"{emoji} <b>{title}</b>\n"
        f"📅 {kst:%Y-%m-%d} ({dow}) {kst:%H:%M} KST\n"
        f"{SEP}"
    )


def section_indices(quotes: list[dict]) -> str:
    if not quotes:
        return ""
    lines = ["<b>📊 지수</b>"]
    for q in quotes:
        pct = q["change_pct"]
        icon = "⚡" if ("VIX" in q["name"] and pct > 0) else _arrow(pct)
        lines.append(f"{icon} {h(q['name'])} {_fmt_pct(pct)}")
    return "\n".join(lines)


def section_macro(quotes: list[dict], spread_10y_3m: float | None = None) -> str:
    if not quotes:
        return ""
    lines = ["<b>🌏 매크로</b>"]
    for q in quotes:
        pct = q["change_pct"]
        val = _fmt_value(q["symbol"], q["close"])
        lines.append(f"{_arrow(pct)} {h(q['name'])} {val} ({_fmt_pct(pct)})")
        # 10년물 줄 바로 아래에 스프레드 표시
        if q["symbol"] == "^TNX" and spread_10y_3m is not None:
            sign = "+" if spread_10y_3m >= 0 else ""
            warn = " ⚠️역전" if spread_10y_3m < 0 else ""
            lines.append(f"    └ 10Y-3M 스프레드 {sign}{spread_10y_3m:.2f}%p{warn}")
    return "\n".join(lines)


def section_fx_korea(quotes: list[dict]) -> str:
    if not quotes:
        return ""
    lines = ["<b>🌐 환율 · 한국 증시 (참고)</b>"]
    for q in quotes:
        pct = q["change_pct"]
        close = q["close"]
        name = q["name"]
        if name == "USD/KRW":
            val = f"{close:,.2f}"
        else:
            val = f"{close:,.2f}"
        lines.append(f"{_arrow(pct)} {h(name)} {val} ({_fmt_pct(pct)})")
    return "\n".join(lines)


def section_sectors(quotes: list[dict]) -> str:
    if not quotes:
        return ""
    lines = ["<b>🏭 섹터 (미 증시 ETF 기준)</b>"]
    for q in quotes:
        pct = q["change_pct"]
        if pct >= 2.0:
            icon = "🚀"
        elif pct <= -2.0:
            icon = "💥"
        else:
            icon = _arrow(pct)
        lines.append(f"{icon} {h(q['name'])} {_fmt_pct(pct)}")
    return "\n".join(lines)


def section_fred_indicators(ind: dict) -> str:
    """FRED 주요 경제 지표 섹션 (일별·월별 혼합)."""
    if not ind:
        return ""
    lines = ["<b>📊 경제 지표</b>"]

    # ── 금리 ──────────────────────────────────────────────────────────────
    rate_parts: list[str] = []
    if ff := ind.get("fedfunds"):
        rate_parts.append(f"기준금리 {ff['value']:.2f}%")
    if d2 := ind.get("dgs2"):
        chg = f"({d2['change']:+.2f}%p)" if d2.get("change") is not None else ""
        rate_parts.append(f"2Y {d2['value']:.2f}% {chg}".strip())
    if d10 := ind.get("dgs10"):
        chg = f"({d10['change']:+.2f}%p)" if d10.get("change") is not None else ""
        rate_parts.append(f"10Y {d10['value']:.2f}% {chg}".strip())
    if (sp := ind.get("spread_10y_2y")) is not None:
        warn = " ⚠️역전" if sp < 0 else ""
        rate_parts.append(f"스프레드 {sp:+.2f}%p{warn}")
    if rate_parts:
        lines.append("💵 금리: " + " · ".join(rate_parts))

    # ── 물가 ──────────────────────────────────────────────────────────────
    infl_parts: list[str] = []
    if (cpi := ind.get("cpi")) and cpi.get("yoy") is not None:
        flag = " 🔴" if cpi["is_recent"] else ""
        infl_parts.append(f"CPI {cpi['yoy']:.1f}%YoY{flag}")
    if (pce := ind.get("core_pce")) and pce.get("yoy") is not None:
        flag = " 🔴" if pce["is_recent"] else ""
        gap = pce["yoy"] - 2.0
        infl_parts.append(f"Core PCE {pce['yoy']:.1f}%YoY (+{gap:.1f}%p 목표대비){flag}")
    if infl_parts:
        lines.append("💹 물가: " + " · ".join(infl_parts))

    # ── 고용 ──────────────────────────────────────────────────────────────
    emp_parts: list[str] = []
    if (ur := ind.get("unrate")) and ur.get("value") is not None:
        flag = " 🔴" if ur["is_recent"] else ""
        chg = f"({ur['mom']:+.1f}%p)" if ur.get("mom") else ""
        emp_parts.append(f"실업률 {ur['value']:.1f}% {chg}{flag}".strip())
    if (nfp := ind.get("nfp")) and nfp.get("mom") is not None:
        flag = " 🔴" if nfp["is_recent"] else ""
        emp_parts.append(f"NFP {nfp['mom']:+.0f}K{flag}")
    if emp_parts:
        lines.append("💼 고용: " + " · ".join(emp_parts))

    # ── 유동성 ────────────────────────────────────────────────────────────
    liq_parts: list[str] = []
    if (m2 := ind.get("m2")) and m2.get("value") is not None:
        yoy_str = f" ({m2['yoy']:+.1f}%YoY)" if m2.get("yoy") is not None else ""
        liq_parts.append(f"M2 ${m2['value']:.1f}T{yoy_str}")
    if (fa := ind.get("fed_assets")) and fa.get("value") is not None:
        flag = " 🔴" if fa["is_recent"] else ""
        liq_parts.append(f"Fed자산 ${fa['value']:.2f}T{flag}")
    if liq_parts:
        lines.append("🏦 유동성: " + " · ".join(liq_parts))

    # ── 신용/위험 ──────────────────────────────────────────────────────────
    if (hy := ind.get("hy_spread")) and hy.get("value") is not None:
        chg = f"({hy['change']:+.2f}%p)" if hy.get("change") is not None else ""
        # HY 스프레드 수준: <3% 낮음(위험선호), 3~5% 보통, >5% 고위험
        level = "낮음 🟢" if hy["value"] < 3 else ("보통 🟡" if hy["value"] < 5 else "높음 🔴")
        lines.append(f"⚡ 신용위험: HY스프레드 {hy['value']:.2f}% {chg} — {level}")

    # ── 경기 동향 ──────────────────────────────────────────────────────────
    if (cfnai := ind.get("cfnai")) and cfnai.get("value") is not None:
        v = cfnai["value"]
        flag = " 🔴" if cfnai["is_recent"] else ""
        signal = "평균 이상 성장" if v > 0 else ("성장 둔화" if v > -0.7 else "침체 위험 ⚠️")
        lines.append(f"🏭 경기동향: Chicago Fed NAI {v:+.2f} ({signal}){flag}")

    # ── 소비 심리 ──────────────────────────────────────────────────────────
    mich = ind.get("michigan")
    retail = ind.get("retail_sales")
    cons_parts: list[str] = []
    if mich and mich.get("value") is not None:
        flag = " 🔴" if mich["is_recent"] else ""
        chg = f"({mich['mom']:+.1f})" if mich.get("mom") else ""
        cons_parts.append(f"Michigan {mich['value']:.1f} {chg}{flag}".strip())
    if retail and retail.get("mom_pct") is not None:
        flag = " 🔴" if retail["is_recent"] else ""
        cons_parts.append(f"소매판매 {retail['mom_pct']:+.1f}%MoM{flag}")
    if cons_parts:
        lines.append("🛒 소비: " + " · ".join(cons_parts))

    # ── 침체 경보 ──────────────────────────────────────────────────────────
    if (sahm := ind.get("sahm")) and sahm.get("value") is not None:
        v = sahm["value"]
        flag = " 🔴" if sahm["is_recent"] else ""
        if v >= 0.5:
            signal = "⚠️ 침체 신호"
        elif v >= 0.3:
            signal = "🟡 주의 구간"
        else:
            signal = "🟢 정상"
        lines.append(f"🚨 Sahm Rule: {v:.2f} ({signal}){flag}")

    if len(lines) <= 1:
        return ""
    lines.append("<i>  🔴 최근 14일 이내 발표</i>")
    return "\n".join(lines)


def section_sentiment(fng: dict | None) -> str:
    if not fng:
        return ""
    score = fng["score"]
    if score < 25:
        icon = "😱"
    elif score < 45:
        icon = "😟"
    elif score < 55:
        icon = "😐"
    elif score < 75:
        icon = "🤑"
    else:
        icon = "🔥"
    prev_wk = fng.get("previous_1_week")
    trend = ""
    if prev_wk is not None:
        diff = score - round(float(prev_wk))
        trend = f" (1주 전 대비 {diff:+d})"
    return (
        "<b>🧠 시장 심리</b>\n"
        f"{icon} Fear & Greed: <b>{score}</b> · {h(fng['rating_kr'])}{trend}"
    )


_IMPACT_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_EARNINGS_HOUR = {"bmo": " 🌅장전", "amc": " 🌙장후", "dmh": ""}


def section_events(economic: list[dict], upcoming_earnings: list[dict]) -> str:
    if not economic and not upcoming_earnings:
        return ""
    lines = ["<b>📅 이번 주 이벤트</b>"]

    if economic:
        lines.append("· 경제 (대표 3개):")
        for e in economic[:3]:
            imp = (e.get("impact") or "").lower()
            icon = _IMPACT_ICON.get(imp, "⚪")
            t = e.get("time", "")[:10]
            lines.append(f"  {icon} {h(e['event'])} ({t})")

    if upcoming_earnings:
        lines.append("· 실적 예정:")
        for e in upcoming_earnings[:5]:
            d = e.get("date", "")
            hour_label = _EARNINGS_HOUR.get((e.get("hour") or "").lower(), "")
            lines.append(f"  • <b>{h(e['symbol'])}</b> ({d}){hour_label}")

    return "\n".join(lines)


def section_earnings_results(yesterday: list[dict], watchlist_quotes: list[dict] | None = None) -> str:
    """전일 발표된 실적 beat/miss 상세 (EPS·매출·서프라이즈·주가반응)."""
    if not yesterday:
        return ""
    lines = ["<b>🏢 전일 실적 결과</b>"]
    quotes_map = {q["symbol"]: q["change_pct"] for q in (watchlist_quotes or [])}
    any_ok = False

    for e in yesterday[:5]:
        sym = e.get("symbol", "")
        eps_est = e.get("eps_estimate")
        eps_act = e.get("eps_actual")
        if eps_est is None or eps_act is None:
            continue
        try:
            eps_est_f = float(eps_est)
            eps_act_f = float(eps_act)
        except (TypeError, ValueError):
            continue
        any_ok = True

        beat = eps_act_f >= eps_est_f
        icon = "✅" if beat else "❌"
        verdict = "Beat" if beat else "Miss"
        # 서프라이즈 %
        if eps_est_f != 0:
            surprise = (eps_act_f - eps_est_f) / abs(eps_est_f) * 100
            surprise_str = f"{surprise:+.1f}%"
        else:
            surprise_str = "N/A"

        lines.append(f"{icon} <b>{h(sym)}</b> EPS {verdict} ({surprise_str} 서프라이즈)")
        lines.append(f"  · EPS 예상 ${eps_est_f:.2f} → 실제 ${eps_act_f:.2f}")

        # 매출 (Finnhub은 USD 달러 단위. 십억 단위로 표시)
        rev_est = e.get("rev_estimate")
        rev_act = e.get("rev_actual")
        if rev_est and rev_act:
            try:
                rev_est_b = float(rev_est) / 1e9
                rev_act_b = float(rev_act) / 1e9
                rev_beat = rev_act_b >= rev_est_b
                rev_verdict = "Beat" if rev_beat else "Miss"
                lines.append(
                    f"  · 매출 예상 ${rev_est_b:.2f}B → 실제 ${rev_act_b:.2f}B ({rev_verdict})"
                )
            except (TypeError, ValueError):
                pass

        # 주가 반응 (watchlist에 있으면)
        if sym in quotes_map:
            pct = quotes_map[sym]
            lines.append(f"  · 주가 반응: {_arrow(pct)} {_fmt_pct(pct)}")

    return "\n".join(lines) if any_ok else ""


def section_memory_quotes(quotes: list[dict]) -> str:
    if not quotes:
        return ""
    lines = ["<b>💾 메모리 섹터</b>"]
    for q in quotes:
        name = q["name"].split("(")[0].strip()
        pct = q["change_pct"]
        lines.append(f"{_arrow(pct)} {h(name)} {_fmt_pct(pct)}")
    return "\n".join(lines)


def section_memory_spot(spot_prices: list[dict]) -> str:
    if not spot_prices:
        return ""
    lines = ["<b>💰 스팟 현물가</b> <i>(DRAMeXchange)</i>"]
    for p in spot_prices:
        pct = p["change_pct"]
        if pct >= 3:
            icon = "🚀"
        elif pct <= -3:
            icon = "💥"
        else:
            icon = _arrow(pct)
        lines.append(f"{icon} {h(p['label'])} ${p['session_avg']:.2f} ({_fmt_pct(pct)})")
    return "\n".join(lines)


def section_trendforce(trendforce_news: list[dict]) -> str:
    if not trendforce_news:
        return ""
    lines = ["<b>📰 TrendForce 리포트</b>"]
    for n in trendforce_news[:3]:
        date_short = _shorten_date(n.get("pub", ""))
        link = n.get("link", "")
        title_html = h(n["title"])
        if link:
            body = f'<a href="{h(link)}">{title_html}</a>'
        else:
            body = title_html
        lines.append(f"· <i>({date_short})</i> {body}")
    return "\n".join(lines)


def _shorten_date(pub: str) -> str:
    # "Tue, 07 Apr 2026" → "Apr 7"
    m = _DATE_RE.search(pub)
    if not m:
        return pub[:10]
    day, mon = m.group(1), m.group(2)
    return f"{mon} {int(day)}"


import re as _re
_DATE_RE = _re.compile(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)")
_TICKER_EXPL_RE = _re.compile(r"^\[([A-Z][A-Z0-9\-\.]+)\]\s+(.+)", _re.MULTILINE)


def _parse_stock_explanations(text: str) -> tuple[dict[str, str], str]:
    """LLM rest 파트에서 [TICKER] 설명 라인을 파싱.
    Returns: (ticker→explanation dict, 핵심뉴스+관전포인트 텍스트)
    """
    # <b>📰 핵심 뉴스</b> 기준으로 앞/뒤 분리
    split_markers = ["<b>📰", "📰 핵심"]
    pre, news_text = text, ""
    for marker in split_markers:
        if marker in text:
            idx = text.index(marker)
            pre, news_text = text[:idx], text[idx:]
            break

    explanations: dict[str, str] = {}
    for m in _TICKER_EXPL_RE.finditer(pre):
        explanations[m.group(1)] = m.group(2).strip()

    return explanations, news_text.strip()


def _mover_line(m: dict, explanations: dict[str, str]) -> str:
    sym = m["symbol"]
    raw_name = m.get("name", "")
    # 회사명 단축 (Inc./Corp./Holdings 등 제거, 20자 이하)
    short = _re.sub(r"\s+(Inc\.?|Corp\.?|Holdings|Co\.?|Ltd\.?|Group|plc).*", "", raw_name).strip()[:20]
    name_str = f" {h(short)}" if short and short != sym else ""
    pct = m["change_pct"]
    badge = " 🚀" if pct >= 3 else (" 💥" if pct <= -3 else "")
    expl = explanations.get(sym, "")
    expl_str = f" — {expl}" if expl else ""
    return f"{_arrow(pct)} <b>{h(sym)}</b>{name_str} {_fmt_pct(pct)}{badge}{expl_str}"


def section_sp500_movers(movers: list[dict], explanations: dict[str, str]) -> str:
    """SP500 등락 TOP 종목을 포매터가 직접 렌더링 (LLM 선택 배제)."""
    if not movers:
        return ""
    gainers = [m for m in movers if m["change_pct"] > 0]
    losers  = [m for m in movers if m["change_pct"] <= 0]
    lines = ["<b>🔥 종목 이슈 (S&P 500 등락 TOP)</b>"]
    if gainers:
        lines.append("📈 <b>상승</b>")
        for m in gainers:
            lines.append(_mover_line(m, explanations))
    if losers:
        lines.append("📉 <b>하락</b>")
        for m in losers:
            lines.append(_mover_line(m, explanations))
    return "\n".join(lines)


_NARRATIVE_BREAK = "===BREAK==="


def _split_narrative(narrative: str) -> tuple[str, str]:
    """LLM 출력을 관심 종목 파트와 나머지로 분리."""
    if _NARRATIVE_BREAK in narrative:
        idx = narrative.index(_NARRATIVE_BREAK)
        return narrative[:idx].strip(), narrative[idx + len(_NARRATIVE_BREAK):].strip()
    return "", narrative.strip()


def compose_brief(
    market: dict,
    narrative: str,
    economic: list[dict] | None = None,
    upcoming_earnings: list[dict] | None = None,
    yesterday_earnings: list[dict] | None = None,
    fng: dict | None = None,
    dram_spot: list[dict] | None = None,
    trendforce_news: list[dict] | None = None,
    sp500_movers: list[dict] | None = None,
    fred_indicators: dict | None = None,
) -> str:
    """08:00 풀 브리핑."""
    focus, rest = _split_narrative(narrative)

    if sp500_movers:
        explanations, news_text = _parse_stock_explanations(rest)
        stock_section = section_sp500_movers(sp500_movers, explanations)
    else:
        stock_section = ""
        news_text = rest

    parts: list[str] = [header("morning")]
    for s in (
        section_indices(market.get("indices", [])),
        section_macro(market.get("macro", []), market.get("spread_10y_3m")),
        section_sectors(market.get("sectors", [])),
        section_sentiment(fng),
        focus,          # 👁 관심 종목 (MU·SNDK)
        section_earnings_results(yesterday_earnings or [], market.get("gainers", []) + market.get("losers", [])),
        stock_section,  # 🔥 종목 이슈 (SP500 TOP)
        news_text,      # 📰 핵심 뉴스 + 💡 관전 포인트
        section_memory_quotes(market.get("memory", [])),
        section_memory_spot(dram_spot or []),
        section_trendforce(trendforce_news or []),
        section_fred_indicators(fred_indicators or {}),  # 📊 경제 지표 (부록)
        section_events(economic or [], upcoming_earnings or []),
    ):
        if s:
            parts.append(s)
    return "\n\n".join(parts) + "\n" + footer()


def compose_midday(
    market: dict,
    narrative: str,
    fng: dict | None = None,
    trendforce_news: list[dict] | None = None,
    futures_quotes: list[dict] | None = None,
) -> str:
    """14:00 중간 업데이트 — 선물 + 최신 뉴스·신규 이슈 중심.
    14시 KST는 미 시장 폐장 상태라 지수·섹터는 전일 데이터와 동일 → 선물로 대체.
    """
    parts: list[str] = [header("midday")]
    for s in (
        section_futures(futures_quotes or []),   # 실시간 선물 방향성
        section_sentiment(fng),
        narrative,  # 🔥 최신 종목 이슈 + 📰 미장 신규 뉴스 + 💡 점심 체크
        section_memory_quotes(market.get("memory", [])),
        section_trendforce(trendforce_news or []),
    ):
        if s:
            parts.append(s)
    return "\n\n".join(parts) + "\n" + footer()


def compose_preview(
    market: dict,
    narrative: str,
    today_earnings: list[dict] | None = None,
    fng: dict | None = None,
    futures_quotes: list[dict] | None = None,
    premarket_movers: list[dict] | None = None,
    **_ignored,
) -> str:
    """22:00 미장 개장 프리뷰.
    선물 지수 + 프리마켓/애프터마켓 종목 움직임 + 오늘 실적·이벤트 중심.
    """
    parts: list[str] = [header("preview")]
    for s in (
        section_futures(futures_quotes or []),
        section_premarket_movers(premarket_movers or []),
        section_earnings_today(today_earnings or []),
        section_sentiment(fng),
        narrative,  # 📰 간밤 뉴스 + 💡 개장 체크 (LLM이 프리마켓 섹션은 생성 안 함)
    ):
        if s:
            parts.append(s)
    return "\n\n".join(parts) + "\n" + footer()


def section_premarket_movers(movers: list[dict]) -> str:
    """프리/애프터마켓 종목 움직임 (실제 시세 기반)."""
    if not movers:
        return ""
    # 소스 혼합되어 있으면 제목에 표시
    sources = {m.get("source", "") for m in movers}
    src_label = "프리마켓" if sources == {"프리"} else ("애프터마켓" if sources == {"애프터"} else "프리/애프터마켓")
    lines = [f"<b>🔥 {src_label} 주요 움직임</b>"]
    for m in movers:
        pct = m["change_pct"]
        if pct >= 3:
            icon = "🚀"
        elif pct <= -3:
            icon = "💥"
        else:
            icon = _arrow(pct)
        src_tag = f" <i>({m['source']})</i>" if len(sources) > 1 else ""
        lines.append(f"{icon} <b>{h(m['symbol'])}</b> ${m['price']:.2f} ({_fmt_pct(pct)}){src_tag}")
    return "\n".join(lines)


def section_futures(quotes: list[dict]) -> str:
    if not quotes:
        return ""
    lines = ["<b>📈 미 지수 선물 (오버나이트)</b>"]
    for q in quotes:
        pct = q["change_pct"]
        lines.append(f"{_arrow(pct)} {h(q['name'])} {_fmt_pct(pct)}")
    return "\n".join(lines)


def section_earnings_today(today_earnings: list[dict]) -> str:
    """오늘 예정된 실적 발표 종목만 표시 (preview 전용)."""
    if not today_earnings:
        return ""
    lines = ["<b>🏢 오늘 실적 예정</b>"]
    for e in today_earnings[:8]:
        d = e.get("date", "")
        hour_label = _EARNINGS_HOUR.get((e.get("hour") or "").lower(), "")
        lines.append(f"• <b>{h(e['symbol'])}</b> ({d}){hour_label}")
    return "\n".join(lines)


def section_events_today(economic: list[dict], today_earnings: list[dict]) -> str:
    """오늘 (미국 시간 기준) 한정 이벤트 섹션 — preview 전용."""
    if not economic and not today_earnings:
        return ""
    from datetime import date
    today = date.today().isoformat()
    # 경제 지표 — 오늘 & 내일 위주 (KST 22시 = 미국 9시 전이라 오늘자 데이터 중요)
    lines = ["<b>📅 오늘·내일 이벤트</b>"]
    today_econ = [e for e in economic if today <= e.get("time", "")[:10] <= f"{today[:8]}{int(today[8:])+2:02d}"][:6]
    if today_econ:
        lines.append("· 경제:")
        for e in today_econ:
            imp = (e.get("impact") or "").lower()
            icon = _IMPACT_ICON.get(imp, "⚪")
            t = e.get("time", "")[:10]
            lines.append(f"  {icon} {h(e['event'])} ({t})")
    if today_earnings:
        lines.append("· 오늘 실적 예정:")
        for e in today_earnings[:6]:
            d = e.get("date", "")
            hour_label = _EARNINGS_HOUR.get((e.get("hour") or "").lower(), "")
            lines.append(f"  • <b>{h(e['symbol'])}</b> ({d}){hour_label}")
    return "\n".join(lines) if len(lines) > 1 else ""


def compose_weekend(
    narrative: str,
    fng: dict | None = None,
    trendforce_news: list[dict] | None = None,
) -> str:
    """주말 브리핑 — 뉴스·이슈 중심, 시세 데이터 없음."""
    parts: list[str] = [header("weekend")]
    for s in (
        section_sentiment(fng),
        narrative,  # 📰 주말 주요 뉴스 + 💡 다음 주 체크포인트
        section_trendforce(trendforce_news or []),
    ):
        if s:
            parts.append(s)
    return "\n\n".join(parts) + "\n" + footer()


def footer() -> str:
    return SEP
