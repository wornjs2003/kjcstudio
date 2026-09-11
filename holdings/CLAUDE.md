# KJC Holdings 프로젝트

## 성격
- KJC Studio 메인 사이트의 하위 구역이지만 **독립 프로젝트**로 취급
- 보유 종목 관리 + 주식 분석 서비스(구 KJCEngine)
- 나중에 별도 레포/사이트로 분리 예정 (서브도메인 or 전용 GitHub Pages)

## 자립 원칙 (중요)
- holdings 내부에서는 `../assets/`, `../data/`, `../partials/` 등 **부모 사이트 리소스 절대 참조 금지**
- 모든 CSS/JS/이미지/데이터는 `holdings/` 내부에만 존재
- 디자인 변수는 부모 사이트에서 **복사**해 사용 (공유 link 금지)
- 메인 사이트로 돌아가는 링크는 허용 (`../index.html` 또는 절대 URL)
- 이 폴더를 통째로 다른 레포에 복사해도 그대로 동작해야 함

## 파일 구조 (holdings 를 루트로 간주)

화면은 두 장입니다. 토스증권 구성을 참고해 잡았습니다 (2026-09-11).

- `index.html` : **첫 화면** — 지수 · 종목 목록 · 고른 종목 미리보기
- `stock.html` : **종목 화면** — `?code=005930` 으로 종목을 정한다. 차트 · 호가 · 매매 기록 · 메모
- `analysis/index.html` : 주식 분석 (구 KJCEngine)
- `roadmap.html` : 개발 로드맵 · `status.html` : 연결 상태 확인

CSS — 색과 모서리는 `css/theme.css` 한 곳에서만 정한다
- `css/theme.css`  : **색 · 모서리 · 글꼴 단일 기준**
- `css/frame.css`  : 두 화면이 함께 쓰는 틀 (관심 사이드바 · 세로 바 · 시세 띠)
- `css/home.css`   : 첫 화면 전용 · `css/stock.css` : 종목 화면 전용
- `css/h-page.css` : analysis · roadmap 서브 페이지용

JS
- `js/home.js`  : 첫 화면 엔트리 · `js/stock.js` : 종목 화면 엔트리
- `js/components/frame.js` : 관심 사이드바 · 세로 바 · 시세 띠 · 시세 갱신 루프
- `js/chart.js` : 캔들 차트 (TradingView Lightweight Charts)
- `js/theme.js` : 차트가 쓸 색을 theme.css 에서 읽어온다
- `js/data/market.js` : 종목·지수 **목록** (코드·이름·섹터·회사색). 시세는 여기 두지 않는다
- `js/data/live.js`   : 서버(/api/kis/*) 에서 시세 받아오기
- `js/store/memo.js`  : 종목 메모 (브라우저 저장)
- `js/utils/format.js`: 숫자 표기 (원 · 조원 · 배 · 만주 · ▲▼)
- `js/h-page.js` : 서브 페이지 nav/footer 주입

그 밖
- `partials/` : 서브 페이지용 네비·푸터 · `sw.js` : 개발용 서비스 워커
- `server/kis_proxy.py` : 로컬 개발 서버 + KIS 중계 · `worker/` : 배포용 Cloudflare Worker

## 디자인 규칙
- 테마: **라이트 테마** — 토스증권 팔레트 (바탕 #f6f7f9 · 카드 #ffffff), 2026-09-11 변경
- **색은 `css/theme.css` 한 곳에서만 정한다.** base/layout/components/h-page 에는 색 정의를 두지 않는다
- 색상 하드코딩 금지. `--kh-*`(대시보드) · `--h-*`(서브 페이지) 변수만 `var()` 로 쓴다
- 차트 색(`js/chart.js`)은 canvas 라 CSS 를 상속받지 못하므로 따로 맞춰야 한다
- accent: #3182f6 (토스 블루). 하락색도 같은 파랑 — 토스 팔레트에 파랑이 하나뿐
- 상승 #f04452 / 하락 #3182f6 (한국식). 모서리 8 / 12 / 16px
- 면 구조: **회색 바탕 + 흰 카드**. 테두리는 거의 쓰지 않는다
- 폰트: Noto Sans KR, Roboto
- 메인 사이트와 시각적 일관성 유지하되, 파일은 별도 소유


## 데이터 규칙 (중요)
- **예시 데이터를 화면에 두지 않는다.** 받아온 값만 보여주고, 없으면 없다고 적는다
- 이유: 그럴듯한 숫자가 박혀 있으면 연결이 안 된 건지 시세가 그런 건지 구분할 수 없다 (2026-09-11 지시)
- 빈 값 표기: `불러오는 중` (요청 중) · `—` (받아올 곳이 아직 없음) · `불러오지 못함` (실패)
- 아직 붙이지 않은 기능은 `js/components/empty-state.js` 의 `notConnected()` 로
  "무엇이 비어 있는지 + 무엇을 붙이면 채워지는지" 를 화면에 적는다
- `js/data/market.js` 에는 목록(코드·이름·섹터)만 둔다. 시세·재무는 서버에서 받는다

## 실행
- 루트에서 단축: `../holdings-preview.command`
- 독립 실행: `./preview.command` (이 파일은 분리 시 함께 이동)
- 포트: 8765

## 응답 규칙
- 사용자 호칭은 항상 "재권님"
- 항상 존댓말
- 한국어만 사용 (작업 진행 상태 메시지 포함)

## 작업 확인 규칙
- 수정 후 반드시 재권님이 브라우저로 확인할 수 있는 상태까지 만들어서 넘길 것
- 로컬 서버 실행 또는 스크린샷 제공 필수
