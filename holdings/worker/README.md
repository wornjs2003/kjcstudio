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

## 4. workers.dev 재활성화 주의

- Worker 코드를 수정해 다시 배포하면 `workers.dev` 주소가 되살아날 수 있다
  (Cloudflare 문서: 대시보드에서 껐어도 Wrangler 설정이 없으면 배포 시 다시 켜짐)
- 코드 배포 후에는 `Settings > Domains & Routes` 에서 비활성 상태인지 확인할 것
