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
- `index.html` : 보유 종목 대시보드 (진입점, 기존 sidebar 앱 UI 유지)
- `analysis/index.html` : 주식 분석 페이지 (구 KJCEngine 모달이 페이지로 승격)
- `roadmap.html` : 주식 분석 서비스 로드맵
- `engine/` : 구 KJCEngine 문서 (CLAUDE.md, ROADMAP.md, SETUP.md, docs/)
- `css/base.css`, `css/layout.css`, `css/components.css` : 대시보드용 기존 스타일
- `css/h-page.css` : analysis/roadmap 서브 페이지 공통 스타일
- `js/main.js` : 대시보드 엔트리 (ES module, components/ 로드)
- `js/components/` : 대시보드 컴포넌트 (sidebar, index-strip, news-feed 등)
- `js/store/`, `js/utils/`, `js/data/` : 상태/유틸/목업 데이터
- `js/h-page.js` : 서브 페이지(analysis/roadmap) 공통 nav/footer 주입
- `js/analysis.js` : 주식 분석 페이지 로직 (네이버 금융)
- `partials/nav.html`, `partials/footer.html` : 서브 페이지용 네비/푸터 조각
- `data/` : 지수/관심종목 초기값 등
- `sw.js` : 서비스 워커
- `preview.command` : 독립 실행 파일 (분리 시 따라감)

## 디자인 규칙
- 테마: 다크 테마 (#0c0c0e)
- accent: #4f7eff
- 폰트: Noto Sans KR, Roboto
- 메인 사이트와 시각적 일관성 유지하되, 파일은 별도 소유

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
