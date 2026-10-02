---
name: main-guard
description: 메인 자리(메인 폴더의 데이터와 8765 서버)를 건드리는 일이면 반드시 읽는다. market.db · holdings/data · secrets · 토큰 캐시 · 8765 재시작 · install.command · launchd 메인 등록이 전부 여기 걸린다. 재권님 허락 없이는 손대지 않는다.
when_to_use: market.db · 메인 DB · 8765 · 재시작 · 올리기 · install.command · launchctl · kis-proxy.plist · KJC_DB_PATH · journal_mode · WAL · holdings/data · secrets.json · 토큰 캐시 · 「메인에서 재 보자」 · 「메인 걸로 돌려 보자」 가 나올 때. 시험 코드가 메인 경로를 가리키려 할 때도 이 룰이다.
---

# 메인 자리는 재권님 허락 없이 건드리지 않는다

재권님 말씀 그대로다 (2026-10-01).

> 메인쪽은 **내 허락없이 절대 건들면 안되는곳**이야 안정장치를 여러개 만들어줘

## 무엇이 메인 자리인가

메인 폴더 `/Users/kjc/work/KJCStudio` 와 **서비스방 `/Users/kjc/service`**(재권님 「범위에 넣어줘」 · 외부접속이 보는 자리)의
**데이터와 돌고 있는 것**이다. 소스 코드는 아니다 — 그것은 레인 룰이 본다.

| | 무엇 |
|---|---|
| 데이터 | 두 폴더의 `holdings/market.db`(과 `-wal` · `-shm`) · `holdings/data/` 전부 · `holdings/secrets.json` · `holdings/.kis-token-cache.json` |
| 돌고 있는 것 | **8765 · 8764** 프로세스 — 재시작 · 죽이기 · `install.command` 로 올리기 · launchd 등록(`kr.kjcstudio.kis-proxy` · `kr.kjcstudio.service-8764`) |
| 서비스방 작업 트리 | `git -C /Users/kjc/service merge · checkout · reset · pull` — 옮기기는 `service-deploy.command` 로만, 그것도 `KJC_MAIN_OK=1` 을 붙여(지시 길 · 켜기) |

**폴더가 아니라 경로다.** 2026-10-01 에 한 세션이 **자기 폴더(kjc-dev3)에서** 시험 코드에 `KJC_DB_PATH` 로 메인
DB 절대 경로를 적어 쓰기 모드로 열었고, `journal_mode` 가 WAL 로 바뀌었다. 메인 폴더에 있지 않아도 닿는다.

## 하는 법

1. **읽는 것은 된다.** `ls` · `cat` · `grep` · `git` 조회 · `sqlite3 -readonly` · `SELECT` — 훅이 지나가게 둔다.
2. **쓰거나 가리키거나 올리고 내리는 것은 먼저 여쭙는다.** 무엇을 · 왜 · 되돌리는 법 · 알림이 나가는지를 한 줄로.
   세션 폴더의 자기 DB(`kjc-stock/holdings/market.db` 등)로 되는 일이면 **거기서 한다** — 메인을 가리킬 이유가 없다.
3. **허락을 받았으면 그 명령 앞에 `KJC_MAIN_OK=1` 을 붙인다.** 훅은 그 표시를 「허락받았다」 로 읽고 지나가며
   **`logs/main-ok.log` 에 한 줄 남긴다.** 받지 않고 붙이면 룰 위반이고 그 목록(`check-rules.py` 가 센다)에서 드러난다 —
   기계가 허락을 못 보는 자리라 **그 표시가 곧 세션의 서명**이다. 헛걸림(글자만 있는데 막힘)에는 붙이지 않는다 —
   경로를 조각으로 적거나 파일에서 읽는다.
4. **사고가 났으면 되돌리지 말고 먼저 알린다.** 되돌리는 것도 메인을 건드리는 일이다.

## 무엇이 막나 — 안전장치 넷

| | 어디 | 무엇을 |
|---|---|---|
| 훅 ① | `tools/hook-main-guard.py` (PreToolUse Bash · Edit · Write) | 경로가 **인자**로 오면 읽기 명령 목록만 통과(그 밖은 막음) · 글 안의 경로는 닿는 동사(`open w` · `connect` ro 없음 · `KJC_DB_PATH` · 리다이렉트)만 · 프로세스는 닫힌 집합(`install.command` 포트 없음/8765/8764 · `service-deploy.command` · `launchctl` 메인·서비스방 · kill 계열 · 이름으로 죽이기). 메인 데이터 파일 편집도 막는다. **막는 메시지가 `-readonly` · `mode=ro` 길을 알려 준다.** `KJC_MAIN_OK=1` 사용은 `logs/main-ok.log` 에 남긴다 |
| 설정 ② | `.claude/settings.json` 의 `deny` | 자주 쓰는 모양 몇을 **묻지도 않고** 막는다 — 훅이 안 돌아도 남는 겹. `sqlite3` 는 여기 안 둔다(읽기까지 막는다) |
| 검사 ③ | `python3 tools/check-rules.py` | 훅 등록 · 훅 파일 · 이 스킬이 **빠지면 위반**으로 낸다 — 장치가 조용히 꺼지는 것을 잡는다 |
| 룰 ④ | `CLAUDE.md` 「메인 자리는 재권님 허락 없이 건드리지 않는다」 | 세션이 시작할 때 읽는다 |

**훅은 걸림돌이지 자물쇠가 아니다.** 명령 모양을 바꾸면 빠져나간다. 그래서 룰이 함께 있다.

## 못 막는 것

- **8765 서버 자신이** 쓰는 것 — 그것은 정상이다.
- 세션 밖(사람이 터미널에서) 하는 일.
- 소스 코드 편집 — 메인 폴더에서 일하는 세션(개념정의 · 개발2 · 작업우선순위)이 자기 레인 파일을 고치는 것은
  막지 않는다. **다만 그 코드가 재시작 때 로드된다** — 「재시작은 커밋 안 된 코드도 로드한다」.
