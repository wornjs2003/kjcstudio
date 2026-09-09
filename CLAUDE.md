# KJC Studio 프로젝트

## 기본 정보
- 회사명: KJC Studio
- 이메일: contact@kjcstudio.kr
- 전화: 02-1234-5678
- 주소: 서울특별시 강남구 테헤란로 123, KJC 빌딩 5층

## 사이트 성격
- 크리에이티브 스튜디오 포트폴리오 사이트
- 메인페이지 열면 대표 카테고리 작업물 갤러리가 바로 보임
- 참고 레퍼런스: https://0yanggang.imweb.me/21 (레이아웃 차용, 테마는 다크 유지)

## 디자인 규칙
- 테마: 다크 테마 유지 (흰 배경 사용 금지)
- 배경색: #0c0c0e
- accent 색상: #4f7eff
- 폰트: Noto Sans KR, Roboto
- 카테고리 제목: 거대 이탤릭 타이포
- 작업물 갤러리: 매저너리(비정형) 그리드
- 스타일 기조: 미니멀, 프로페셔널

## 호스팅
- GitHub 저장소: https://github.com/wornjs2003/kjcstudio
- 배포 주소: https://wornjs2003.github.io/kjcstudio/
- GitHub 푸시하면 자동 반영

## 파일 구조
- `index.html` : 메인 (대표 카테고리 갤러리 = 3D Modeling)
- `category/` : 카테고리 페이지 (3d-modeling, ai-work, web-interactive, branding)
- `about.html`, `services.html`, `contact.html` : 서브 페이지 (상단 ⋯ 더보기 접근)
- `assets/css/`, `assets/js/`, `assets/images/`, `assets/fonts/` : 메인 사이트 전용 리소스
- `data/categories.json` : 카테고리 목록, 대표 카테고리 지정
- `data/works.json` : 모든 작업물 데이터 (이곳만 수정하면 갤러리 자동 반영)
- `partials/nav.html`, `partials/footer.html` : 공통 네비/푸터 (fetch로 동적 주입)
- `holdings/` : 독립 프로젝트 구역 (주식 분석, 보유 종목 — 별도 관리)

## 상단 메뉴 구성
- 3D Modeling / AI Work / Web·Interactive / Branding / Holdings → / ⋯(더보기)
- ⋯ 안에 About / Services / Contact
- Holdings는 `holdings/` 로 외부 이동 느낌 (화살표 아이콘)

## 확장 규칙
- 작업물 추가(권장): 이미지를 `assets/images/works/<카테고리>/` 에 드롭 → 루트 `refresh-works.command` 더블클릭 → `data/works.json` 자동 갱신
- 작업물 추가(수동): `data/works.json` 에 항목 한 개 직접 추가 (스크립트 안 써도 됨)
- 카테고리 추가: `data/categories.json` 에 추가 + `category/` 에 쌍둥이 HTML 1개 복사 + `tools/refresh-works.py` 의 `CATEGORIES` 배열에 추가
- 공통 UI(네비/푸터) 변경: `partials/` 파일 한 곳만 수정

## 이미지 파일명 규칙 (refresh-works.command 용)
- 기본: `elf-warrior.jpg` → 제목 "Elf Warrior", span 자동 (Pillow 있을 때 비율 분석)
- 순서 지정: `01_elf-warrior.jpg` → order=1
- span 강제: `elf-warrior_tall.jpg` / `_wide.jpg` / `_square.jpg` / `_large.jpg`
- 조합: `02_엘프전사_wide.jpg` → order=2, 제목 "엘프전사"(한글 유지), span=wide
- 한글 파일명 가능, 공백 대신 `-` 또는 `_` 사용

## holdings 폴더 규칙 (중요)
- holdings는 **독립 프로젝트**로 취급. 나중에 별도 레포/사이트로 분리 예정
- 메인 사이트 → holdings 링크는 허용, holdings → 메인 사이트 리소스 참조는 금지
- holdings는 자체 `assets/`, `data/`, `partials/`, `CLAUDE.md` 를 소유
- 디자인 변수는 holdings 쪽에 복제해서 공유 (단일 소스 의존 금지)
- holdings 관련 룰은 `holdings/CLAUDE.md` 참조

## 실행 커맨드
Mac 은 `.command` 더블클릭, Windows 는 같은 이름의 `.bat` 더블클릭. 동작은 동일.

| 용도 | Mac | Windows |
|---|---|---|
| 메인 사이트 (포트 8080) | `studio-preview.command` | `studio-preview.bat` |
| holdings 단축 (포트 8765) | `holdings-preview.command` | `holdings-preview.bat` |
| holdings 독립 실행 | `holdings/preview.command` | `holdings/preview.bat` |
| 작업물 목록 갱신 | `refresh-works.command` | `refresh-works.bat` |

- 브라우저: Chrome 우선, 없으면 기본 브라우저
- 두 OS 모두 Python 3 필요 (Windows: Python 3.13 + Pillow 설치됨)

## 작업 환경 (2대 병행)
- Mac 과 Windows PC(`C:\work\KJCStudio`) 양쪽에서 작업. 동기화는 GitHub 저장소 기준
- 다른 PC 로 옮겨 작업 시작 전 `git pull`, 끝나면 `git push` 로 맞출 것
- 줄바꿈은 `.gitattributes` 로 LF 고정 (`.bat` 만 CRLF). OS 바꿔도 전체 파일이 변경된 것처럼 보이지 않음
- `tools/refresh-works.py` 는 `newline="\n"` 으로 저장하므로 Windows 에서 돌려도 diff 가 깨지지 않음

## 이미지 최적화 권장
- 포맷: JPG (사진/렌더) · PNG (투명도 필요 시) · WebP (최고 압축률)
- 가로 크기: 1200~1800px (매저너리 그리드 2~3열 기준 충분)
- 파일 크기: 장당 500KB 이하 권장 (GitHub Pages 로딩 속도)
- 색공간: sRGB

## 응답 규칙
- 사용자 호칭은 항상 "재권님"으로 부를 것
- 항상 존댓말로 답변할 것
- 영어 혼용 금지, 한국어로만 답변할 것
- 생각중·작업중·수정중 등 모든 진행 상태 표시 메시지는 영어 금지, 반드시 한국어로 표시할 것
- 파일/코드 편집, 검색, 도구 호출 등 내부 작업 라벨도 모두 한국어로 표시할 것

## 작업 확인 규칙 (중요)
- 작업을 시키면 확인을 꼭 한다.
- 작업의 완성을 재권님이 확인할 수 있도록 한다.
- 작업의 완성을 확인한다는 것은 "실행을 해서 재권님이 눈으로 볼 수 있어야 한다"는 뜻이다.
- 코드만 작성하고 "되어 있을 것입니다"로 끝내지 말 것.
- 코드 수정 후에는 반드시 재권님이 화면으로 결과를 확인할 수 있는 상태(실행 중인 페이지, 열려 있는 브라우저 등)까지 만들어서 넘길 것.
- 실행 환경이 막히면 대안을 끝까지 찾아서 재권님이 결과를 볼 수 있게 할 것 (로컬 서버, 단일 HTML, 스크린샷, 직접 열어주기 등).
