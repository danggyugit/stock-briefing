# 🎯 목적

매일 아침 전일 미국 증시 상황(지수·매크로·종목·뉴스)을 Gemini API로 요약해 Telegram으로 자동 전송.

---

# 🗂️ 구조

| 파일 | 역할 |
|---|---|
| `main.py` | 파이프라인 진입점 (수집 → 요약 → 전송) |
| `config.py` | 환경변수·추적 티커·모델 설정 |
| `collectors/market.py` | yfinance 지수/매크로/종목 시세 |
| `collectors/news.py` | Finnhub 뉴스 (폴백: Yahoo RSS) |
| `summarizer.py` | Gemini 2.0 Flash로 한국어 브리핑 생성 |
| `notifier.py` | Telegram 전송 (HTML, 4000자 단위 분할) |
| `register_scheduler.bat` | Windows 작업 스케줄러 매일 07:00 등록 |
| `logs/` | 생성된 브리핑 텍스트·오류 로그 |

---

# 🔑 환경 변수 (.env)

| 변수 | 용도 | 필수 |
|---|---|:---:|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | ✅ |
| `TELEGRAM_BOT_TOKEN` | @BotFather로 봇 생성 후 발급 | ✅ |
| `TELEGRAM_CHAT_ID` | 본인 chat_id (getUpdates로 확인) | ✅ |
| `FINNHUB_API_KEY` | https://finnhub.io/register (선택) | ❌ |

---

# 🚀 실행

```bash
cd c:/Users/sk15y/claude/stock_briefing
pip install -r requirements.txt
cp .env.example .env   # 값 채워넣기

# 단위 테스트
python -m collectors.market    # 시세 수집만
python -m collectors.news      # 뉴스 수집만
python notifier.py             # Telegram 연결 확인

# 전체 파이프라인
python main.py

# 매일 자동 실행 등록
register_scheduler.bat
```

---

# 📝 브리핑 포맷

1. 📊 지수 한눈에 — 주요 지수 흐름
2. 🌏 매크로 — 금리/달러/원유/금/비트코인
3. 🔥 종목 이슈 — 움직임 큰 종목 배경
4. 📰 핵심 뉴스 — 시장 영향 이슈
5. 💡 오늘의 관전 포인트 — 한국 투자자 체크리스트

---

# ❌ 금지

- `ANTHROPIC_API_KEY` 사용 금지 — 이 프로젝트는 무료 API만 사용
- 근거 없는 수치·예측을 요약에 포함 금지 (프롬프트로 차단)
- 종목 추천·매매 신호 제공 금지 (정보 전달만)
