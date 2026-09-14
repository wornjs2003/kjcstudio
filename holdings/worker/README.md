# KIS 중계 서버 배포 안내 (Cloudflare Workers)

`kis-worker.js` 를 Cloudflare 에 올려서 `thekjcstudio.com/api/kis/*` 로 동작시키는 절차입니다.

앱키는 이 저장소에도, 코드에도, 브라우저에도 들어가지 않습니다.
Cloudflare Secret 으로만 저장되며 **재권님이 직접 입력**합니다.

---

## 1. KV 네임스페이스 만들기 (접근토큰 보관용)

KIS 접근토큰은 24시간짜리인데 1분에 한 번만 발급할 수 있습니다.
그래서 발급받은 토큰을 어딘가 보관해야 하고, 그 장소가 KV 입니다.

1. Cloudflare 대시보드 → **Storage & Databases** → **KV**
   (또는 좌측 메뉴에서 `Workers KV`)
2. **Create instance** 클릭
3. 이름: `kjc-kis-kv`
4. **Create**

---

## 2. Worker 만들기

1. Cloudflare 대시보드 → **Workers & Pages**
2. **Create application** → **Create Worker**
3. 이름: `kjc-kis-proxy`
4. **Deploy** (기본 코드 그대로 일단 배포)
5. 배포 후 **Edit code** 클릭
6. 편집기 내용을 전부 지우고, `kis-worker.js` 전체를 붙여넣기
7. **Deploy**

> 로컬 파일 위치: `holdings/worker/kis-worker.js`

---

## 3. 앱키 등록 (Secret) — 재권님이 직접

Worker 화면 → **Settings** → **Variables and Secrets**

| 이름 | 종류 | 값 |
|---|---|---|
| `KIS_APP_KEY` | Secret | 발급받은 App Key |
| `KIS_APP_SECRET` | Secret | 발급받은 App Secret |
| `KIS_MODE` | Text | `prod` (실전) 또는 `vts` (모의) |

- **Secret** 으로 넣으면 저장 후 다시 볼 수 없습니다. 정상입니다.
- `KIS_MODE` 만 일반 Text 로 넣습니다.

---

## 4. KV 연결 (Binding)

Worker 화면 → **Bindings** → **Add binding** → **KV namespace**

| 항목 | 값 |
|---|---|
| Variable name | `KIS_KV` |
| KV namespace | `kjc-kis-kv` |

이름이 정확히 `KIS_KV` 여야 코드가 찾습니다.

---

## 4-2. D1 데이터베이스 연결 (차트·재무 저장용)

차트는 과거 데이터가 필요한데 볼 때마다 KIS 를 부르면 호출량을 감당할 수 없다.
한 번 받은 일봉을 D1 에 쌓아두고 이후에는 DB 에서 꺼내 쓴다.

**만들기**

Cloudflare 대시보드 → D1 SQL database → **Create Database**

| 항목 | 값 |
|---|---|
| 이름 | `kjc-stock-db` |

**연결하기**

Worker 화면 → **Bindings** → **Add binding** → **D1 database**

| 항목 | 값 |
|---|---|
| Variable name | `KJC_DB` |
| D1 database | `kjc-stock-db` |

이름이 정확히 `KJC_DB` 여야 코드가 찾는다.

**테이블 만들기** (최초 1회)

```
https://thekjcstudio.com/api/kis/db/init
```

`{"ok":true,"data":{"created":3}}` 가 나오면 완료.

**무료 한도** (공식 문서 확인)

| 항목 | 한도 |
|---|---|
| 읽기 | 500만 / 일 |
| 쓰기 | 10만 / 일 |
| 저장 | 5 GB |

---

## 5. 도메인에 연결 (Route)

Worker 화면 → **Settings** → **Domains & Routes** → **Add** → **Route**

| 항목 | 값 |
|---|---|
| Route | `thekjcstudio.com/api/*` |
| Zone | `thekjcstudio.com` |

`www` 도 쓰신다면 `www.thekjcstudio.com/api/*` 를 하나 더 추가합니다.

---

## 6. 확인

브라우저에서 (로그인된 상태로) 접속:

```
https://thekjcstudio.com/api/kis/health
```

## 엔드포인트 목록

| 경로 | 하는 일 |
|---|---|
| `/api/kis/health` | 연결·토큰·DB 상태 |
| `/api/kis/price?code=005930` | 종목 현재가 |
| `/api/kis/prices?codes=005930,000660` | 여러 종목 현재가 |
| `/api/kis/indices` | 지수 (KOSPI·KOSDAQ·KOSPI200) + 일봉 |
| `/api/kis/chart?code=005930&days=120` | 일봉 캔들 (DB 우선, 없으면 KIS 에서 받아 저장) |
| `/api/kis/db/init` | 테이블 생성 (최초 1회) |
| `/api/kis/db/status` | 저장 현황 (행 수·종목 수·기간) |
| `/api/kis/stats` | 캐시 설정값 |

`chart` 응답의 `meta.source` 로 어디서 온 데이터인지 알 수 있다.

- `KIS+DB` — KIS 에서 새로 받아 저장함
- `DB` — 저장된 것에서 바로 응답 (KIS 호출 0회)

정상이면 이런 응답이 보입니다.

```json
{"ok":true,"configured":true,"mode":"prod","modeLabel":"실전투자","tokenOk":true,"runtime":"workers"}
```

`ok:false` 이면 `error` 항목에 원인이 한국어로 표시됩니다.

---

## 보안 메모

- 이 Worker 는 `thekjcstudio.com/api/*` 에 붙으므로 **Cloudflare Access 뒤**에 있습니다.
  로그인하지 않은 사람은 API 를 호출할 수 없습니다.
- 앱키는 Secret 으로만 존재하고 응답에 절대 포함되지 않습니다.
- 오류 메시지에도 키가 노출되지 않도록 요약만 전달합니다.

## 호출량

- 시세 응답은 10초, 지수 일봉은 10분 동안 Cloudflare 엣지에서 캐시됩니다.
- 종목 조회는 순차 처리하여 KIS 초당 건수 제한을 넘지 않게 했습니다.
- 실제 호출량은 Cloudflare 대시보드 → Workers → 해당 Worker → 분석에서 확인합니다.

---

# 남은 작업

## 0. 배포해야 반영됩니다 — 2026-09-14 기준 두 가지가 밀려 있습니다

`worker/kis-worker.js` 는 고쳐져 있지만 **대시보드에 붙여넣어 Deploy 해야** 실제로 바뀝니다.
아래 둘이 아직 배포되지 않았습니다.

### (1) 차트가 안 나오던 것 — 고침

메인 화면에서 미리보기 차트만 안 나오고 종목 화면은 나오던 문제입니다.

**원인** — Worker 에 KIS 호출 간격 제어가 없었습니다. 메인 화면은 열릴 때
지수 3건 + 시세 8건 + 분봉 채우기 13~24건을 한꺼번에 쏩니다. 분봉 쪽이 초당 한도에
걸려 실패했고, `fetchMinutesDay` 의 `catch {}` 가 그 실패를 삼켜서 "데이터가 없나 보다"
하고 넘어갔습니다. 그래서 D1 에 봉이 한 개도 쌓이지 않았습니다
(2026-09-14 `/api/kis/health` 에서 `rows: 0` 확인).

**고친 것**
- `kisPace()` — KIS 호출 사이 200ms(초당 5건). 기본 한도 20건의 1/4
- `fetchMinutesDay` 가 실패 건수와 마지막 이유를 돌려주고, 차트 응답 `meta.warn` 에 실린다

로컬(`server/kis_proxy.py`)은 1초 간격이라 이 문제가 없었습니다. 그래서 로컬만 보면
멀쩡해 보였습니다.

### (2) 공시 — 붙임

`/api/dart/disclosures` · `/api/dart/status` · `/api/dart/poll` · `/api/dart/universe`
네 경로와 `scheduled()` 핸들러가 들어갔습니다.

**로컬(server/dart.py)과 다른 점 하나** — 기업 대응표(`corpCode.xml`)를 받지 않습니다.
ZIP 이라 Workers 에서 풀려면 압축 해제를 직접 구현해야 하는데, 정작 화면에 쓰이지 않습니다.
공시 목록(`list.json`)이 종목코드와 회사명을 이미 줍니다.

### 배포 절차 (대시보드)

1. `worker/kis-worker.js` 전체를 복사해 Worker 편집기에 붙여넣고 **Deploy**
2. **Settings > Variables and Secrets** 에 Secret 세 개 추가
   `DART_API_KEY` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID`
   (키는 재권님이 직접 입력하십시오. 세션 간 메시지로 주고받지 않습니다)
3. **Settings > Triggers > Cron Triggers** 에 5분마다 실행을 추가
   — 반영까지 **최대 15분** 걸립니다. 바로 안 돌아도 고장이 아닙니다
4. 배포 후 `workers.dev` 가 Disabled 인지 확인
5. `/api/dart/status` 로 `configured` · `telegram` · `universe` 확인

wrangler 는 쓰지 않습니다. `wrangler.toml` 없이 배포하면 Route·환경변수가 날아가고
`workers.dev` 가 되살아납니다 (2026-09-14 공식 문서 확인).

### 알림이 두 번 갈 수 있습니다

배포하면 **로컬 서버와 Worker 가 둘 다** 텔레그램을 보냅니다. 같은 공시를 두 번 받게 됩니다.
Worker 는 24시간 돌고 로컬은 PC 를 켰을 때만 도니, **Worker 쪽만 남기는 편**이 맞습니다.
로컬을 끄려면 `holdings/secrets.json` 의 `telegram` 항목을 지우면 됩니다
(수집과 화면은 그대로 돌고 알림만 꺼집니다).

### 감시 대상 200종목이 양쪽에서 조금 다를 수 있습니다

로컬과 Worker 가 네이버 시가총액 순위를 따로 부르므로 경계(200위 근처)가 몇 종목
어긋날 수 있습니다. **알림에는 영향이 없습니다** — 알림은 관심종목 8개
(`DART_WATCH_CODES` / `WATCH_CODES`)에만 가고, 그 목록은 양쪽에 같은 값으로 박혀 있습니다.
차이가 나는 것은 화면에 보이는 "최근 공시" 목록의 가장자리뿐입니다.

## 1. 로그인 실패 시 재시도 문제 (추후 수정 필요)

**증상**: 이메일을 잘못 입력했거나, 인증 코드를 다시 받았을 때 접속이 되지 않는 경우가 있음.

**확인된 사실** (Cloudflare 공식 문서 기준)
- PIN 은 요청 후 **10분** 후 만료된다
- PIN 은 일회용이며, 새 PIN 을 요청하면 이전 PIN 은 무효화된다
- 잘못된 코드 → `That account does not have access.`
- 이미 쓴 코드 → `This One-Time PIN has already been used`
- 새 코드는 `Request new code` 버튼으로 재요청

**확인하지 못한 것**
- 재시도 횟수 제한 여부 (문서에 명시 없음)
- 연속 실패 시 일시 차단 여부 (문서에 언급 없음)

**해야 할 일**
- 실제로 재현해서 어느 지점에서 막히는지 확인
- 메일 오타 시의 동작 확인 (정책에 없는 주소를 넣으면 코드 자체가 안 오는지)
- 필요하면 안내 문구를 커스텀 로그인 페이지에 추가

## 2. API 경로 정리

- 현재 `thekjcstudio.com/api/kis/*`
- `thekjcstudio.com/holdings/api/kis/*` 로 옮길 예정 (holdings 를 별도 레포로 분리할 때를 대비)
- 고쳐야 할 곳: Worker 코드의 경로 판단, `js/data/live.js`, `analysis/index.html`, Cloudflare Route 패턴

## 3. Access 애플리케이션 분리

- 지금은 사이트 전체가 한 덩어리라, 이메일을 추가하면 그 사람이 주식창·설립 체크리스트·API 까지 전부 접근한다
- 포트폴리오만 공개하려면 애플리케이션을 둘로 나눠야 한다
  - 포트폴리오: `/` (holdings·api 제외) — 보여줄 사람들
  - 개인 도구: `/holdings/*`, `/api/*` — 재권님만
- **외부에 링크를 주기 전에 처리할 것**

## 5. Route 가 겹칠 때 — 구체적인 패턴이 이긴다

저희 Route 는 `thekjcstudio.com/api/*` 라서 `/api/board` 같은 다른 경로도 범위에 듭니다.
Cloudflare 공식 문서(Workers > Configuration > Routing > Routes)에 따르면
**더 구체적인 패턴이 이깁니다** — `example.com/hello/*` 가 `example.com/*` 를 이깁니다.

그래서 다른 Worker 가 `thekjcstudio.com/api/board*` 로 등록하면 그쪽 요청만 그 Worker 로 가고,
`/api/kis/*` 는 이 Worker 가 계속 처리합니다. 이쪽에서 바꿀 것은 없습니다.
(2026-09-11, projects 보드 작업 세션이 문서에서 확인해 공유)

## 5. 종목명이 업종명으로 나오는 문제 (미루기로 함 — 2026-09-12 지시)

`server/kis_proxy.py` 의 `fetch_price` 가 종목명 자리에 **업종명**을 담는다.

```python
"name": o.get("bstp_kor_isnm"),   # 삼성전자·SK하이닉스 둘 다 "전기·전자"
```

**확인한 것** — `inquire-price`(FHKST01010100) 응답 80개 필드를 전수 확인했다.
**종목명 필드가 아예 없다.** 이름처럼 보이는 것은 넷뿐이고 전부 다른 값이다.

| 필드 | 값 | 정체 |
|---|---|---|
| `rprs_mrkt_kor_name` | KOSPI200 | 대표 시장명 |
| `bstp_kor_isnm` | 전기·전자 | 업종명 (지금 잘못 쓰는 것) |
| `fcam_cnnm` | 100 | 액면가 |
| `cpfn_cnnm` | 7,780 억 | 자본금 |

**확인하지 못한 것** — 종목명을 주는 KIS API(국내주식 기본조회)의 경로·`tr_id`.
공식 문서로 확인한 뒤 진행할 것.

**지금 화면에는 영향 없음** — `index.html`·`stock.html` 은 종목명을 `js/data/market.js`
목록에서 가져온다. 서버 응답만 틀린 값을 담고 있다.

**할 일** — 로드맵 Phase 4 의 "종목 마스터 구축" 과 같은 작업이므로 거기서 함께 처리한다.
그 전까지 급하면 `name` 을 `None` 으로 두는 편이 낫다
(holdings/CLAUDE.md 의 "없으면 없다고 적는다" 규칙).

## 4. workers.dev 재활성화 주의

- Worker 코드를 수정해 다시 배포하면 `workers.dev` 주소가 되살아날 수 있다
  (Cloudflare 문서: 대시보드에서 껐어도 Wrangler 설정이 없으면 배포 시 다시 켜짐)
- 코드 배포 후에는 `Settings > Domains & Routes` 에서 비활성 상태인지 확인할 것
