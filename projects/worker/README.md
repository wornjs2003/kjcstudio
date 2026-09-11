# 프로젝트 보드 저장 서버 배포 안내 (Cloudflare Workers)

`board-api.js` 를 Cloudflare 에 올려서 `thekjcstudio.com/api/board` 로 동작시키는 절차입니다.

보드 내용이 브라우저가 아니라 **서버에 저장**되므로, PC 에서 적은 것이 Mac·휴대폰에서도 그대로 보입니다.

KIS 워커(`holdings/worker/`)를 만드실 때와 **거의 같은 절차**입니다. 다른 점만 표시해 두었습니다.

---

## 준비물 확인

이미 되어 있는 것 (따로 하실 일 없음)

- Cloudflare 계정과 `thekjcstudio.com` 연결
- Cloudflare Access 로 사이트 전체 잠금 — 허용된 이메일만 접속 가능
- Worker 만들고 D1 연결해 본 경험 (KIS 워커)

---

## 1. 데이터베이스 만들기

기존 `kjc-stock-db` 를 쓰지 않고 **새로 하나 만듭니다.** 주식 데이터와 섞이지 않게 하기 위해서입니다.

1. Cloudflare 대시보드 → **Storage & Databases** → **D1 SQL database**
2. **Create Database**
3. 이름: `kjc-board-db`
4. **Create**

> 표(테이블)는 따로 만들지 않아도 됩니다. 서버가 첫 요청 때 알아서 만듭니다.
> KIS 워커처럼 `db/init` 을 부를 필요가 없습니다.

---

## 2. Worker 만들기

1. Cloudflare 대시보드 → **Workers & Pages**
2. **Create application** → **Create Worker**
3. 이름: `kjc-board-api`
4. **Deploy** (기본 코드 그대로 일단 배포)
5. 배포 후 **Edit code**
6. 편집기 내용을 전부 지우고 `board-api.js` 전체를 붙여넣기
7. **Deploy**

> 로컬 파일 위치: `projects/worker/board-api.js`

---

## 3. 데이터베이스 연결

Worker 화면 → **Bindings** → **Add binding** → **D1 database**

| 항목 | 값 |
|---|---|
| Variable name | `BOARD_DB` |
| D1 database | `kjc-board-db` |

이름이 정확히 `BOARD_DB` 여야 코드가 찾습니다.

---

## 4. 변수 두 개 넣기

Worker 화면 → **Settings** → **Variables and Secrets**

**Secret 이 아니라 일반 Text 로** 넣습니다. 비밀번호가 아니라 식별용 값입니다.

| 이름 | 종류 | 값 |
|---|---|---|
| `ACCESS_TEAM` | Text | 팀 이름 (아래 설명) |
| `ACCESS_AUD` | Text | Application Audience 태그 (아래 설명) |

### ACCESS_TEAM 찾는 법

사이트에 로그인할 때 뜨는 **Cloudflare Access 로그인 화면의 주소**를 보시면 됩니다.

```
https://무언가.cloudflareaccess.com/...
        ^^^^^^  ← 이 부분이 팀 이름
```

이 값만 넣습니다. `.cloudflareaccess.com` 은 빼고 앞부분만입니다.

> 대시보드 어느 메뉴에 표시되는지는 제가 공식 문서에서 확인하지 못했습니다.
> 위 방법이 확실하니 그걸로 확인해 주세요.

### ACCESS_AUD 찾는 법 (공식 문서 확인)

**Zero Trust** → **Access controls** → **Applications** → 해당 애플리케이션의 **Configure** → **Additional settings** 에서 복사합니다.

> 이 값은 애플리케이션을 지우고 다시 만들지 않는 한 바뀌지 않습니다.

---

## 5. 주소에 연결 (Route)

Worker 화면 → **Settings** → **Domains & Routes** → **Add** → **Route**

| 항목 | 값 |
|---|---|
| Route | `thekjcstudio.com/api/board*` |
| Zone | `thekjcstudio.com` |

`www` 도 쓰신다면 `www.thekjcstudio.com/api/board*` 를 하나 더 추가합니다.

### KIS 워커와 겹치지 않는 이유

KIS 워커는 `thekjcstudio.com/api/*` 라는 넓은 범위에 붙어 있습니다. 겹쳐 보이지만 문제없습니다.

> 여러 경로 규칙이 동시에 맞을 때는 **가장 구체적인 것이 이긴다** — Cloudflare 공식 문서

`/api/board*` 가 `/api/*` 보다 구체적이므로 보드 요청은 이 Worker 로 옵니다. 나머지 `/api/kis/*` 는 그대로 KIS 워커가 처리합니다.

---

## 6. 확인

브라우저에서 **로그인된 상태로** 접속합니다.

```
https://thekjcstudio.com/api/board/health
```

정상이면 이런 응답이 보입니다.

```json
{
  "ok": true,
  "db": true,
  "accessTeam": true,
  "accessAud": true,
  "signedInAs": "본인@이메일.com",
  "error": null
}
```

| 나온 값 | 뜻 |
|---|---|
| `db: false` | 3단계 D1 연결이 안 됐습니다 |
| `accessTeam` 또는 `accessAud` 가 `false` | 4단계 변수가 빠졌습니다 |
| `signedInAs: null` | 토큰을 못 읽었습니다. `error` 항목을 보세요 |
| `error` 에 문구가 있음 | 그 내용이 원인입니다 (한국어로 표시됩니다) |

여기까지 되면 보드 화면(`https://thekjcstudio.com/projects/`)을 열었을 때
왼쪽 위 표시가 **`서버에 저장됨`** 으로 바뀝니다.

---

## 엔드포인트

| 경로 | 하는 일 |
|---|---|
| `/api/board/health` | 설정 상태 확인 |
| `GET /api/board` | 내 보드 불러오기 |
| `PUT /api/board` | 내 보드 저장하기 |

---

## 동작 방식

```
브라우저 (Access 로그인 완료)
   │  요청에 CF_Authorization 토큰이 자동으로 붙음
   ▼
thekjcstudio.com/api/board
   │  Cloudflare Access 가 먼저 걸러냄
   ▼
Worker (kjc-board-api)
   │  토큰 서명을 검증하고 이메일을 확인
   ▼
D1 (kjc-board-db)  — 보드 전체를 한 줄에 저장
```

**이메일별로 따로 저장됩니다.** 나중에 Access 에 다른 사람을 추가해도 각자 자기 보드를 갖습니다.

---

## 저장 부담

보드 전체를 JSON 한 덩어리로 **한 줄에** 저장합니다. 저장 한 번에 1행만 쓰입니다.

| 항목 | 무료 한도 (공식 문서 확인) | 예상 사용량 |
|---|---|---|
| Worker 요청 | 10만 / 일 | 1,000 미만 |
| D1 쓰기 | 10만 행 / 일 | 1,000 행 미만 |
| D1 읽기 | 500만 행 / 일 | 수십 |
| D1 저장 용량 | 5 GB | 1 MB 미만 |

타이핑할 때마다 보내지 않고 **1초 모아서 한 번** 보냅니다. 한도에 닿을 일이 없습니다.

---

## 서버가 없어도 동작합니다

이 Worker 를 아직 안 올리셨거나 잠시 죽어도 보드는 그대로 쓸 수 있습니다.

| 상황 | 화면 표시 | 동작 |
|---|---|---|
| 서버 정상 | `서버에 저장됨` | 어느 기기에서나 같은 내용 |
| 서버 없음·실패 | `이 브라우저에만 저장됨` | 이 브라우저에만 저장 (예전 방식) |

브라우저 저장은 **항상 함께** 이뤄지므로, 서버가 실패해도 적던 내용이 사라지지 않습니다.

---

## 보안 메모

- 이 Worker 는 `thekjcstudio.com/api/board*` 에 붙으므로 **Cloudflare Access 뒤**에 있습니다. 로그인하지 않은 사람은 호출할 수 없습니다.
- 그 위에 **토큰 서명 검증**을 한 겹 더 넣었습니다. 공식 문서에 "헤더만 확인하는 것으로는 충분하지 않으며, 신원 위조를 막으려면 JWT 와 서명을 반드시 검증해야 한다" 고 되어 있기 때문입니다.
- **주의할 점**: 지금 Access 는 사이트 전체가 **하나의 애플리케이션**으로 묶여 있습니다. 누군가의 이메일을 추가하면 그 사람이 포트폴리오·주식창·설립 체크리스트·프로젝트 보드를 **전부** 보게 됩니다. 보드만 따로 공유하시려면 Access 애플리케이션을 먼저 분리해야 합니다.

---

## 되돌리기

서버 저장을 그만두고 예전처럼 브라우저 저장만 쓰시려면 Worker 의 Route 를 지우면 됩니다. 화면은 자동으로 `이 브라우저에만 저장됨` 으로 돌아가고, 그동안 쌓인 내용은 D1 에 그대로 남아 있습니다.
