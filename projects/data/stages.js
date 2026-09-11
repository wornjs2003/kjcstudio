/* ==========================================================================
   KJC Studio · 프로젝트 관리 — 단계 / 카테고리 정의
   ── 진행 단계나 카테고리를 바꾸려면 이 파일만 고치면 됩니다.
   ── 저장 후 브라우저 새로고침하면 바로 반영됩니다.

   주의: STAGES 의 id 는 저장 키로 쓰입니다.
         기존 id 를 바꾸면 그 단계의 체크가 풀리니 새 단계는 id 를 새로 만드세요.
   ========================================================================== */

/* 프로젝트 진행 단계 — 왼쪽부터 순서대로 진행됩니다 */
const STAGES = [
  { id: "inquiry",  label: "문의 접수", short: "문의" },
  { id: "quote",    label: "견적 발송", short: "견적" },
  { id: "contract", label: "계약 체결", short: "계약" },
  { id: "deposit",  label: "선금 입금", short: "선금", money: true },
  { id: "work",     label: "작업 진행", short: "작업" },
  { id: "draft",    label: "1차 납품",  short: "1차" },
  { id: "revise",   label: "수정 반영", short: "수정" },
  { id: "final",    label: "최종 납품", short: "최종" },
  { id: "balance",  label: "잔금 입금", short: "잔금", money: true }
];

/* 작업 카테고리 — 메인 사이트 카테고리와 맞춰 두었습니다 */
const CATEGORIES = [
  { id: "3d-modeling",    label: "3D Modeling" },
  { id: "ai-work",        label: "AI Work" },
  { id: "web-interactive", label: "Web · Interactive" },
  { id: "branding",       label: "Branding" },
  { id: "etc",            label: "기타" }
];

/* 프로젝트 상태 */
const STATUSES = [
  { id: "active", label: "진행중" },
  { id: "done",   label: "완료" },
  { id: "hold",   label: "보류" }
];

/* 마감 임박 기준 (일) — 이 안에 들면 주황색으로 표시됩니다 */
const DUE_SOON_DAYS = 7;
