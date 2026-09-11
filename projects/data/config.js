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
  { id: "todo",  label: "할 일",  tone: "neutral" },
  { id: "doing", label: "진행중", tone: "accent"  },
  { id: "done",  label: "완료",   tone: "done"    }
];

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
