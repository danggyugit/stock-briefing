# stock_briefing

매일 아침 전일 미국 증시를 요약해 Telegram으로 보내는 자동화 도구. **모든 API가 무료.**

## 빠른 시작 (5단계)

### 1. 패키지 설치
```bash
cd c:/Users/sk15y/claude/stock_briefing
pip install -r requirements.txt
```

### 2. Gemini API 키 발급 (무료)
1. https://aistudio.google.com/apikey 접속 → "Create API key"
2. 발급된 키 복사
3. 하루 1,500회 무료 — 이 프로젝트는 하루 1회만 호출

### 3. Telegram 봇 만들기 (5분)
1. Telegram 앱에서 **@BotFather** 검색 → `/newbot` 입력
2. 봇 이름·username 입력하면 **봇 토큰** 발급됨 (예: `123456:ABC...`)
3. 만든 봇을 **본인이 먼저 /start** 로 말 걸기
4. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 접속
5. 응답에서 `"chat":{"id": 123456789}` 숫자가 본인 **chat_id**

### 4. .env 작성
```bash
cp .env.example .env
```
파일 열어서 `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 채우기.

### 5. 테스트 → 자동 등록
```bash
python notifier.py   # 텔레그램 연결 테스트
python main.py       # 실제 브리핑 한 번 실행

register_scheduler.bat   # 매일 07:00 자동 실행 등록
```

## macOS 자동 실행 (launchd)

Windows 작업 스케줄러 대신 Mac에서는 launchd로 동일한 3개 시간대에 실행한다.

```bash
cd ~/claude/stock-briefing
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # 키 채우기

# plist 등록 (최초 1회) — ~/Library/LaunchAgents/com.danggyu.stockbriefing.{morning,midday,preview}.plist
for m in morning midday preview; do
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.danggyu.stockbriefing.$m.plist
done
```

| 시각 (KST) | Label | 실행 |
|---|---|---|
| 08:00 | `com.danggyu.stockbriefing.morning` | `scripts/launchd/run_brief.sh morning` |
| 14:00 | `com.danggyu.stockbriefing.midday` | `scripts/launchd/run_brief.sh midday` |
| 21:00 | `com.danggyu.stockbriefing.preview` | `scripts/launchd/run_brief.sh preview` |

- 로그: `logs/launchd/<mode>-YYYYMMDD-HHMMSS.log` (30일 보관)
- 즉시 실행: `launchctl kickstart gui/$(id -u)/com.danggyu.stockbriefing.morning`
- 해제: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.danggyu.stockbriefing.morning.plist`
### 잠자기 중 자동 기상 (pmset + wake_chain.sh)

launchd는 잠자기 중엔 실행되지 않으므로 pmset 예약 기상으로 깨운다. **전원 어댑터 연결 + 덮개 열림(또는 클램쉘)** 조건에서만 동작.

`scripts/launchd/wake_chain.sh`가 슬롯 목록을 갖고 있고, 각 슬롯 1분 뒤에 launchd keeper(`com.danggyu.stockbriefing.wake-HHMM`)가 이를 실행한다.
keeper는 (1) 다음 슬롯을 `pmset schedule wake`로 예약하고, (2) grace 시간 동안 caffeinate로 깨어 있다가, (3) stock-dashboard/stock-briefing python 프로세스가 도는 동안 계속 깨어 있고, (4) 끝나면 종료해 Mac이 평소처럼 잠들게 둔다.

| 기상 슬롯 | keeper | grace | 커버하는 job |
|---|---|---|---|
| 01:55 | wake-0156 | 45분 | 02:00 backtest-data, 02:30 preset-backtests(~5.5h, 프로세스 종료까지 유지) |
| 03:55 | wake-0356 | 10분 | 일요일 04:00 forward-returns |
| 06:55 | wake-0656 | 75분 | 07:00~07:30 dashboard 배치, 08:00 morning, 매월 1일 08:00 rebalancing |
| 10:25 | wake-1026 | 10분 | 10:30 rotation-backtest |
| 13:55 | wake-1356 | 10분 | 14:00 midday |
| 20:55 | wake-2056 | 10분 | 21:00 preview |

브리핑 wrapper도 끝날 때 `wake_chain.sh --schedule-only`를 호출해 체인을 한 번 더 보강한다. 로그: `logs/launchd/wake-YYYYMMDD.log`.

**최초 1회 설정 (sudo 필요)**

1. launchd에서는 비밀번호 입력이 불가하므로 pmset만 NOPASSWD 허용:
   ```bash
   sudo install -m 440 scripts/launchd/sudoers-pmset-briefing /etc/sudoers.d/pmset-briefing
   sudo visudo -c
   ```
2. 안전망으로 매일 06:55 반복 기상 등록 (체인이 끊겨도 아침에 재시작):
   ```bash
   sudo pmset repeat wakeorpoweron MTWRFSU 06:55:00
   pmset -g sched   # 확인
   ```

## 무엇이 오는가

```
🇺🇸 전일 미국 증시 브리핑
2026-04-20 (Mon) 07:00 KST
──────────────────────

📊 지수 한눈에
S&P 500은 0.8% 상승 마감. AI 반도체 주도로 나스닥이 …

🌏 매크로
10년물 금리가 4.2%로 하락하며 기술주 강세를 뒷받침 …

🔥 종목 이슈
- NVDA: 신제품 발표 기대로 3% 급등
- TSLA: 배송 지연 보도에 2% 하락
…

📰 핵심 뉴스
- 연준 파월 의장, 금리 인하 시점 시사
- 중동 지정학 리스크 완화 신호
…

💡 오늘의 관전 포인트
반도체 ETF 흐름이 한국 개장에도 영향 예상.
```

## 비용

| 항목 | 비용 |
|---|---|
| Gemini 2.0 Flash | 무료 (일 1,500회) |
| yfinance | 무료 |
| Finnhub (선택) | 무료 (분 60회) |
| Telegram Bot | 무료 |
| **합계** | **월 0원** |
