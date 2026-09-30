/* ==========================================================================
   KJC Studio · 프로젝트 보드 — 설정
   ── 칼럼, 카테고리, 기본 할 일 세트를 여기서 고칩니다.
   ── 저장 후 브라우저 새로고침하면 바로 반영됩니다.

   주의: id 는 저장 키로 쓰입니다.
         기존 id 를 바꾸면 그 칼럼/카테고리에 있던 카드가 갈 곳을 잃습니다.
         새로 만들 때는 새 id 를 쓰세요.
   ========================================================================== */

/* 보드 칼럼 — 왼쪽부터 순서대로 놓입니다
   tone : 제목을 감싸는 배지 색 (neutral 회색 · accent 파랑 · done 초록)
          색 자체는 theme.css 에서 고칩니다 */
const COLUMNS = [
  { id: "todo",   label: "할 일",  tone: "neutral" },
  { id: "doing",  label: "진행중", tone: "accent"  },
  { id: "review", label: "검수중", tone: "neutral" },
  { id: "done",   label: "완료",   tone: "done"    }
];
/* 「검수중」 은 2026-09-30 지시로 넣었습니다 — "완료 앞에 검수라고 하나 더",
   그 뒤 "검수중 창하나만 더 넣고하면 댈듯" 으로 이름이 정해졌습니다.
   **`id` 는 `review` 그대로입니다** — 데이터의 `column` 값이 그것을 씁니다.
   「주식 작업은 두 세션이 검수한다」 가 룰인데 보드에 그 자리가 없었습니다.

   ⚠️ `tone` 이 「할 일」 과 같은 `neutral` 입니다. 배지 색이 셋(neutral·accent·done)
   뿐이라 새 색을 쓰려면 `theme.css` 를 건드려야 하는데, 거기는 네 구역이 함께
   쓰는 자리라 따로 여쭐 일입니다.

   ⚠️ 칼럼을 더하면 요약의 「진행중」 에 들어갑니다 — `updateSummary()` 가
   「가운데 칸들」 을 세기 때문이고, 주석에 그렇게 적혀 있어 의도대로입니다. */

/* 작업 카테고리 — 카드 위쪽 색 띠로 표시됩니다
   색은 theme.css 에 정의된 값을 가져다 씁니다 (색 자체는 theme.css 에서 고치세요) */
const CATEGORIES = [
  { id: "3d-modeling",     label: "3D Modeling",       color: "var(--pj-cat-3d)" },
  { id: "ai-work",         label: "AI Work",           color: "var(--pj-cat-ai)" },
  { id: "web-interactive", label: "Web · Interactive", color: "var(--pj-cat-web)" },
  { id: "branding",        label: "Branding",          color: "var(--pj-cat-branding)" },
  { id: "etc",             label: "기타",               color: "var(--pj-cat-etc)" }
];

/* 기본 작업 세트 — 프로젝트에서 "기본 세트" 를 누르면 할 일 칸에 한 번에 들어갑니다 */
const TODO_TEMPLATE = [
  "레퍼런스 정리",
  "견적 발송",
  "1차 시안 작업",
  "클라이언트 피드백 반영",
  "최종 납품"
];

/* 마감 임박 기준 (일) — 이 안에 들면 주황색으로 표시됩니다 */
const DUE_SOON_DAYS = 7;
