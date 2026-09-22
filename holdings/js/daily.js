/* ==========================================================================
   데일리분석 화면 — 틀

   **그리는 것은 여기 없다.** 내용은 `components/daily-view.js` 가 만든다.
   전용 화면과 모달이 같은 것을 써야 하기 때문이다
   (2026-09-21 지시 — "데일리분석 누르면 페이지 이동하는 게 아니고 모달로").

   이 파일에 남은 것은 **이 화면에만 있는 것**뿐이다 — 세로 아이콘바 ·
   시세 띠 · 시세 갱신 루프. 모달에는 그 셋이 없다.
   ========================================================================== */

/* mountWatchSide 는 부르지 않는다. 이 화면의 오른쪽 칸은 관심종목이 아니라
   보낼 문안이다 (2026-09-16 지시). */
import { mountVBar, startLiveLoop }
  from './components/frame.js';
import { mountDaily } from './components/daily-view.js';

const $ = (id) => document.getElementById(id);

/* 세로 아이콘바에는 아직 이 화면 자리가 없어 아무것도 켜지지 않는다.
   ITEMS 는 components/frame.js 안에 있고 네 화면이 함께 쓴다.
   추가는 주식페이지_개발 에 넘겼다 (2026-09-16). */
mountVBar($('kh-vbar'), 'daily');
startLiveLoop({ prices: true });

/* `.kh-main` 안 — 카테고리 줄 뒤에 붙는다. 감싸는 요소를 새로 두지 않는 것은
   `tools/layout-baseline.json` 이 이 화면의 칸을 클래스 이름으로 세어 두어서다.
   한 겹을 더하면 기준에 없는 칸이 생긴다. */
mountDaily(document.querySelector('.kh-main'), {
  side: $('kh-side'),
});
