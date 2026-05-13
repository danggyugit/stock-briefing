"""Telegram 전송. HTML parse_mode 사용."""
from __future__ import annotations

import html
import time
from pathlib import Path

import requests

TELEGRAM_MSG = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_PHOTO = "https://api.telegram.org/bot{token}/sendPhoto"
MAX_LEN = 4000  # 텔레그램 한 메시지 4096자 제한 대비 여유
CAPTION_LEN = 1020  # sendPhoto caption 최대 1024자
RETRY_ATTEMPTS = 4
RETRY_WAIT = 30  # 초 — 네트워크 부팅 대기용


def _post_with_retry(url: str, **kwargs) -> None:
    last_err: Exception | None = None
    for i in range(RETRY_ATTEMPTS):
        try:
            r = requests.post(url, **kwargs)
            if r.status_code == 429:
                wait = int(r.json().get("parameters", {}).get("retry_after", 5)) + 1
                print(f"[notifier] 429 Flood wait, {wait}초 대기")
                time.sleep(wait)
                continue
            if not r.ok:
                # Telegram 에러 응답 본문 노출
                body = r.text[:300]
                raise requests.HTTPError(f"{r.status_code} {r.reason}: {body}")
            return
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            if i < RETRY_ATTEMPTS - 1:
                print(f"[notifier] 네트워크 오류, {RETRY_WAIT}초 후 재시도 ({i+1}/{RETRY_ATTEMPTS}): {e}")
                time.sleep(RETRY_WAIT)
    if last_err:
        raise last_err


def _escape(text: str) -> str:
    """HTML parse_mode에서 허용되지 않는 문자 이스케이프."""
    return html.escape(text, quote=False)


def _chunks(text: str, size: int = MAX_LEN) -> list[str]:
    out: list[str] = []
    while text:
        if len(text) <= size:
            out.append(text)
            break
        cut = text.rfind("\n", 0, size)
        if cut == -1:
            cut = size
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return out


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """text는 Telegram HTML parse_mode 기준 이미 유효한 HTML이어야 함
    (formatter가 데이터 필드는 escape_html로 이스케이프 처리)."""
    url = TELEGRAM_MSG.format(token=token)
    for chunk in _chunks(text):
        _post_with_retry(
            url,
            data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )


def send_telegram_photo(token: str, chat_id: str, photo_path: Path, caption: str = "") -> None:
    url = TELEGRAM_PHOTO.format(token=token)
    caption = _escape(caption)[:CAPTION_LEN]  # 캡션은 평문 → 이스케이프
    # 파일 bytes를 미리 읽어 전달해야 retry 시 EOF 문제 방지
    data_bytes = photo_path.read_bytes()
    _post_with_retry(
        url,
        data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
        files={"photo": (photo_path.name, data_bytes, "image/png")},
        timeout=60,
    )


if __name__ == "__main__":
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, require
    token = require("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not TELEGRAM_CHAT_IDS:
        raise RuntimeError("TELEGRAM_CHAT_ID 환경변수가 비어 있습니다.")
    for chat in TELEGRAM_CHAT_IDS:
        send_telegram(token, chat, "✅ stock_briefing 테스트 메시지입니다.")
        print(f"전송 완료 → {chat}")
