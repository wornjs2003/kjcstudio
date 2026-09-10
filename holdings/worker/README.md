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
