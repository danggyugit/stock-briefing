"""신규 사용자 chat_id 조회 헬퍼.

사용법:
  1. 새 사용자가 Telegram에서 @Dangstock_bot 검색 → /start 또는 아무 메시지 전송
  2. 이 스크립트 실행:   python add_user.py
  3. 출력된 chat_id를 .env의 TELEGRAM_CHAT_ID에 콤마로 추가
     예) TELEGRAM_CHAT_ID=8079274438,123456789
"""
from __future__ import annotations

import sys

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, require

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    token = require("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
    r.raise_for_status()
    updates = r.json().get("result", [])

    if not updates:
        print("봇에 대화 기록이 없습니다.")
        print("→ 새 사용자에게 @Dangstock_bot 검색 후 /start 보내달라고 요청하세요.")
        return 1

    seen: dict[int, dict] = {}
    for u in updates:
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid and cid not in seen:
            seen[cid] = chat

    print(f"📋 봇과 대화한 사용자 {len(seen)}명:\n")
    print(f"{'chat_id':<15} {'이름':<20} {'상태'}")
    print("-" * 55)
    for cid, info in seen.items():
        name = info.get("first_name", "") + " " + info.get("last_name", "")
        status = "✅ 등록됨" if str(cid) in TELEGRAM_CHAT_IDS else "➕ 추가 가능"
        print(f"{cid:<15} {name.strip():<20} {status}")

    print(f"\n현재 .env TELEGRAM_CHAT_ID: {','.join(TELEGRAM_CHAT_IDS) or '(비어있음)'}")
    print("\n신규 사용자를 추가하려면:")
    print("  1. 위 목록에서 '➕ 추가 가능' 상태의 chat_id 복사")
    print("  2. .env 파일 열기")
    print("  3. TELEGRAM_CHAT_ID 줄에 콤마로 이어 붙이기")
    print("     예) TELEGRAM_CHAT_ID=8079274438,123456789")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
