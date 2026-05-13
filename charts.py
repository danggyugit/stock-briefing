"""matplotlib으로 자산 가격 추이 차트 PNG 생성."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import yfinance as yf

# Windows 한글 폰트 — Malgun Gothic 우선
plt.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def make_chart(name: str, symbol: str, out_dir: Path, period: str = "1mo") -> Path | None:
    """종가 라인 차트를 PNG로 저장해 경로 반환. 실패 시 None."""
    try:
        hist = yf.Ticker(symbol).history(period=period, auto_adjust=False)
        if hist.empty or len(hist) < 2:
            print(f"[chart] {symbol} 데이터 부족")
            return None

        closes = hist["Close"]
        latest = float(closes.iloc[-1])
        start = float(closes.iloc[0])
        change_pct = (latest - start) / start * 100

        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
        color = "#2563eb" if change_pct >= 0 else "#dc2626"
        ax.plot(closes.index, closes.values, linewidth=2.2, color=color)
        ax.fill_between(closes.index, closes.min() * 0.995, closes.values, alpha=0.12, color=color)

        ax.set_title(f"{name} ({symbol})  |  {latest:,.2f}  {change_pct:+.2f}% ({period})",
                     fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, alpha=0.25, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.autofmt_xdate()
        fig.tight_layout()

        safe = symbol.replace("=", "").replace("^", "")
        out_path = out_dir / f"chart_{safe}_{datetime.now():%Y%m%d_%H%M%S}.png"
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path
    except Exception as e:
        print(f"[chart] {symbol} 실패: {e}")
        return None


def make_charts(specs: list[tuple[str, str]], out_dir: Path, period: str = "1mo") -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for name, symbol in specs:
        p = make_chart(name, symbol, out_dir, period=period)
        if p:
            out.append((f"{name} ({period})", p))
    return out


def make_sector_heatmap(sector_quotes: list[dict], out_dir: Path) -> Path | None:
    """11개 GICS 섹터 ETF 일일 등락률을 막대 차트로."""
    if not sector_quotes:
        return None
    try:
        # 등락률 내림차순 정렬 (이미 정렬돼 있을 가능성 높지만 안전차원)
        rows = sorted(sector_quotes, key=lambda q: q["change_pct"])
        names = [q["name"].replace("(XLK)", "").replace("(XLC)", "").replace("(XLY)", "")
                 .replace("(XLF)", "").replace("(XLI)", "").replace("(XLV)", "")
                 .replace("(XLP)", "").replace("(XLE)", "").replace("(XLU)", "")
                 .replace("(XLB)", "").replace("(XLRE)", "") for q in rows]
        vals = [q["change_pct"] for q in rows]
        colors = ["#16a34a" if v >= 0 else "#dc2626" for v in vals]

        fig, ax = plt.subplots(figsize=(9, 5.5), dpi=110)
        bars = ax.barh(names, vals, color=colors, edgecolor="white", linewidth=0.8)
        ax.axvline(0, color="gray", linewidth=0.8)
        for bar, v in zip(bars, vals):
            x = bar.get_width()
            ha = "left" if x >= 0 else "right"
            offset = 0.05 if x >= 0 else -0.05
            ax.text(x + offset, bar.get_y() + bar.get_height() / 2,
                    f"{v:+.2f}%", va="center", ha=ha, fontsize=10, fontweight="bold")

        ax.set_title("미 증시 섹터 등락률 (당일)", fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, axis="x", alpha=0.25, linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.margins(x=0.15)
        fig.tight_layout()

        out_path = out_dir / f"chart_sectors_{datetime.now():%Y%m%d_%H%M%S}.png"
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path
    except Exception as e:
        print(f"[chart] 섹터 히트맵 실패: {e}")
        return None


def make_spot_history_chart(
    history: dict[str, list[tuple[str, float]]],
    out_dir: Path,
    min_points: int = 3,
    normalized: bool = False,
) -> Path | None:
    """로컬 CSV 누적 데이터로 스팟 현물가 추이 차트.
    normalized=True면 시작일 100 기준으로 정규화 (스케일 통일).
    """
    if not history:
        return None

    filtered = {p: v for p, v in history.items() if len(v) >= min_points}
    if not filtered:
        print(f"[chart] 스팟 history 부족 — 제품별 최소 {min_points}일 필요")
        return None

    try:
        import datetime as dt
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=110)
        for prod, series in filtered.items():
            dates = [dt.date.fromisoformat(d) for d, _ in series]
            prices = [p for _, p in series]
            latest = prices[-1]
            first = prices[0]
            pct = (latest - first) / first * 100 if first else 0

            if normalized:
                values = [p / first * 100 if first else 100 for p in prices]
                label = f"{prod} ({pct:+.1f}%)"
            else:
                values = prices
                label = f"{prod} (${latest:.2f}, {pct:+.1f}%)"

            ax.plot(dates, values, linewidth=2.0, marker="o", markersize=4, label=label)

        if normalized:
            ax.axhline(100, linestyle="--", color="gray", alpha=0.5, linewidth=1)
            ax.set_ylabel("시작일 = 100")
            title = f"DRAM/NAND 스팟 현물가 정규화 추이 ({len(next(iter(filtered.values())))}일 누적)"
        else:
            ax.set_ylabel("USD")
            title = f"DRAM/NAND 스팟 현물가 추이 ({len(next(iter(filtered.values())))}일 누적)"
        ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, alpha=0.25, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.legend(loc="best", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.autofmt_xdate()
        fig.tight_layout()

        suffix = "_norm" if normalized else ""
        out_path = out_dir / f"chart_spot_history{suffix}_{datetime.now():%Y%m%d_%H%M%S}.png"
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path
    except Exception as e:
        print(f"[chart] 스팟 history 차트 실패: {e}")
        return None


def make_basket_chart(specs: list[tuple[str, str]], title: str, out_dir: Path, period: str = "3mo") -> Path | None:
    """여러 종목을 시작일=100 정규화하여 한 차트에 오버레이."""
    if not specs:
        return None
    try:
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=110)
        plotted = 0
        for name, sym in specs:
            hist = yf.Ticker(sym).history(period=period, auto_adjust=False)
            if hist.empty or len(hist) < 2:
                continue
            closes = hist["Close"]
            norm = closes / closes.iloc[0] * 100
            final_pct = norm.iloc[-1] - 100
            ax.plot(closes.index, norm, linewidth=2.0,
                    label=f"{name} ({sym}) {final_pct:+.1f}%")
            plotted += 1
        if plotted == 0:
            plt.close(fig)
            return None
        ax.axhline(100, linestyle="--", color="gray", alpha=0.5, linewidth=1)
        ax.set_title(f"{title} — 시작일 100 기준 ({period})",
                     fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, alpha=0.25, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.legend(loc="upper left", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.autofmt_xdate()
        fig.tight_layout()

        out_path = out_dir / f"chart_basket_{datetime.now():%Y%m%d_%H%M%S}.png"
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path
    except Exception as e:
        print(f"[chart] 바스켓 차트 실패: {e}")
        return None


if __name__ == "__main__":
    from config import CHART_SYMBOLS, CHART_PERIOD, LOG_DIR
    results = make_charts(CHART_SYMBOLS, LOG_DIR, CHART_PERIOD)
    for caption, path in results:
        print(f"- {caption}: {path}")
