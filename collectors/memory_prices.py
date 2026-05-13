"""DRAMeXchange 스팟 가격 스크래핑 + TrendForce 메모리 뉴스 RSS + 로컬 history 누적.

DXI·30일 차트는 MI 멤버십 전용이라 불가. 대신 매일 스팟가 CSV에 저장해 자체 트렌드 생성.
"""
from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

DRAM_URL = "https://www.dramexchange.com/"
TRENDFORCE_RSS = "https://www.trendforce.com/feed/Semiconductors.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 추적할 대표 제품 (제품명 정확 매칭)
TRACK_PRODUCTS = [
    ("DDR5 16Gb 4800/5600", "DDR5 16Gb (2Gx8) 4800/5600"),
    ("DDR4 16Gb 3200", "DDR4 16Gb (2Gx8) 3200"),
    ("DDR4 8Gb 3200", "DDR4 8Gb (1Gx8) 3200"),
    ("NAND MLC 64Gb", "MLC 64Gb 8GBx8"),
]

MEMORY_NEWS_KEYWORDS = [
    "DRAM", "NAND", "SSD", "DDR5", "DDR4", "HBM",
    "memory price", "memory contract", "flash memory", "NAND flash",
]


def fetch_dram_spot_prices() -> list[dict]:
    """DRAMeXchange 홈페이지에서 제품별 스팟 평균가·변동률 추출.
    실패하거나 특정 제품 매칭 안 되면 해당 항목은 제외.
    """
    try:
        r = requests.get(DRAM_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"[memory_prices] DRAMeXchange 실패: {e}")
        return []

    out: list[dict] = []
    for label, pattern in TRACK_PRODUCTS:
        # 제품명 위치 찾기 → 이후 HTML 블록에서 5번째 tab_tr_gray (Session Avg) + 변동률 추출
        m = re.search(re.escape(pattern) + r".*?(?:<tr|$)", html, re.DOTALL)
        if not m:
            continue
        block = m.group(0)
        # tab_tr_gray 셀들에서 숫자만 추출
        cells = re.findall(r'<td[^>]*class="tab_tr_gray"[^>]*>\s*([\d.,]+)\s*</td>', block)
        if len(cells) < 5:
            continue
        try:
            session_avg = float(cells[4].replace(",", ""))
        except ValueError:
            continue

        # 변동률: "\d+\.\d+ %" + 방향 이미지 (up.gif/down.gif/stable.gif)
        direction_match = re.search(r'src="[^"]*(up|down|stable)\.gif"', block)
        pct_match = re.search(r'>\s*(-?\d+\.\d+)\s*%', block)
        if not pct_match:
            continue
        pct = float(pct_match.group(1))
        if direction_match and direction_match.group(1) == "down":
            pct = -abs(pct)
        elif direction_match and direction_match.group(1) == "up":
            pct = abs(pct)

        out.append({"label": label, "session_avg": session_avg, "change_pct": pct})

    # 마지막 업데이트 시각
    update_match = re.search(r'Last Update[^<]*<[^>]*>([^<]+)</', html)
    last_update = update_match.group(1).strip() if update_match else ""

    return out


def fetch_trendforce_memory_news(limit: int = 5) -> list[dict]:
    """TrendForce Semiconductors RSS에서 메모리 관련 뉴스 추출."""
    try:
        r = requests.get(TRENDFORCE_RSS, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"[memory_prices] TrendForce RSS 실패: {e}")
        return []

    pat = re.compile("|".join(re.escape(k) for k in MEMORY_NEWS_KEYWORDS), re.IGNORECASE)
    out: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        if not pat.search(title + " " + desc):
            continue
        # 제목이 너무 길면 … 로 자르기 (Telegram HTML 길이 부담)
        short = title if len(title) <= 120 else title[:117] + "..."
        out.append({"title": short, "link": link, "pub": pub[:16]})
        if len(out) >= limit:
            break
    return out


HISTORY_COLUMNS = ["date", "product", "session_avg", "change_pct"]


def append_spot_history(spot: list[dict], csv_path: Path) -> None:
    """오늘 스팟가를 CSV에 append. 동일 날짜+제품은 덮어쓰기.
    해당 제품 이력이 전무할 경우 change_pct로 어제 가격을 역산해 초기 시딩.
    """
    if not spot:
        return
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    existing: list[dict] = []
    existing_products: set[str] = set()
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("date") == today and row.get("product") in {p["label"] for p in spot}:
                    continue  # 오늘자 재기록은 스킵 (새값으로 덮어쓰기)
                existing.append(row)
                existing_products.add(row.get("product", ""))

    new_rows: list[dict] = []
    for p in spot:
        # 이력이 전혀 없는 제품이면 어제 가격을 change_pct로 역산해서 먼저 추가
        if p["label"] not in existing_products:
            pct = p["change_pct"] or 0
            try:
                prev_price = p["session_avg"] / (1 + pct / 100) if pct != -100 else p["session_avg"]
                new_rows.append(
                    {
                        "date": yesterday,
                        "product": p["label"],
                        "session_avg": round(prev_price, 3),
                        "change_pct": "",  # 역산값이라 변동률 공란
                    }
                )
            except (ZeroDivisionError, TypeError):
                pass
        new_rows.append(
            {
                "date": today,
                "product": p["label"],
                "session_avg": p["session_avg"],
                "change_pct": p["change_pct"],
            }
        )

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        w.writeheader()
        for row in existing:
            w.writerow({k: row.get(k, "") for k in HISTORY_COLUMNS})
        for row in new_rows:
            w.writerow(row)


def load_spot_history(csv_path: Path) -> dict[str, list[tuple[str, float]]]:
    """제품별 (날짜, 가격) 리스트 반환."""
    if not csv_path.exists():
        return {}
    out: dict[str, list[tuple[str, float]]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            prod = row.get("product", "")
            try:
                price = float(row.get("session_avg", 0))
            except ValueError:
                continue
            out.setdefault(prod, []).append((row.get("date", ""), price))
    # 날짜 오름차순 정렬
    for prod in out:
        out[prod].sort(key=lambda x: x[0])
    return out


if __name__ == "__main__":
    print("=== DRAM/NAND 스팟가격 ===")
    for p in fetch_dram_spot_prices():
        sign = "+" if p["change_pct"] >= 0 else ""
        print(f"  {p['label']}: ${p['session_avg']:.3f} ({sign}{p['change_pct']:.2f}%)")
    print("\n=== TrendForce 메모리 뉴스 ===")
    for n in fetch_trendforce_memory_news():
        print(f"  [{n['pub']}] {n['title']}")
