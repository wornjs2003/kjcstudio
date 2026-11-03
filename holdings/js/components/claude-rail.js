/* ==========================================================================
   오른쪽 Claude 줄 · 창 (2026-11-03 재권님 「화면 오른쪽에 항상 따라다니는 세로로 긴 창 하나도 추가해줘. 그창에 버튼을 누르면
   claude 와 연동되도록 개발 할거야」 → 「세로로 긴줄이 있고 아이콘을 눌렀을때 열리도록」 → 그림 넷 「응 맞아」)

   넓은 창 — 오른쪽 세로 줄(아이콘)이 늘 보이고, 누르면 창이 열려 본문을 그만큼 민다.
   폰     — 오른쪽 아래 둥근 단추 · 누르면 창이 화면 전체.
   본문을 미는 폭은 html 의 --kh-rail-w 하나다(줄 + 열린 창) — home.js 창 맞춤(fitScale)이 그 폭을 빼고 배율을 푼다.
   열림 · 닫힘은 이 브라우저에만 기억한다(보는 자리 기억 — 「화면이 가져도 되는 것」).

   Claude 연동은 아직 없다 — 대화 자리는 빨간 바탕(미정) · 입력 · 바로 묻기는 눌리지 않는다. 연동을 붙이면 여기를 채운다.
   ========================================================================== */

const KEY = 'kh-claude-rail-open';
const WIDE = '(min-width: 768px)';
const ICON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z"/></svg>';
const QUICK = ['이 종목 요약', '오늘 시장 왜 빠졌나', '지금 뜨는 산업 설명'];

function load() { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } }
function save(v) { try { localStorage.setItem(KEY, v ? '1' : '0'); } catch { /* 저장 못 해도 화면은 그대로 */ } }

/* 「보고 있는 것」 — 첫 화면 큰 칸이 시장 지도면 그 이름, 아니면 큰 차트 */
function context() {
  const hm = document.querySelector('.kh-hm:not([hidden]) .kh-hm-title');
  return '홈 · ' + (hm?.textContent.trim() || '큰 차트');
}

export function mountClaudeRail() {
  const wide = matchMedia(WIDE);
  const root = document.documentElement;

  const bar = document.createElement('nav');
  bar.className = 'kh-rail-bar';
  bar.setAttribute('aria-label', 'Claude');
  bar.innerHTML = `<button type="button" class="kh-rail-ic" title="Claude">${ICON}</button>`;

  const fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'kh-rail-fab';
  fab.title = 'Claude';
  fab.innerHTML = ICON;

  const panel = document.createElement('aside');
  panel.className = 'kh-rail-panel';
  panel.hidden = true;
  panel.innerHTML = `<div class="kh-rail-hd"><b>Claude</b><span class="kh-rail-st">연결 예정</span>
      <button type="button" class="kh-rail-x" title="닫기" aria-label="닫기">×</button></div>
    <div class="kh-rail-ctx">보고 있는 것 — <b class="kh-rail-now"></b><br>단추를 누르면 이 화면을 함께 보냅니다</div>
    <!-- 미정: Claude 연동 전 — 대화가 쌓일 자리 -->
    <div class="kh-rail-body">대화가 여기 쌓입니다<br>아직 Claude 와 연결하지 않았습니다 — 연동을 붙이면 채워집니다</div>
    <div class="kh-rail-quick">${QUICK.map((q) => `<button type="button" disabled>${q}</button>`).join('')}</div>
    <div class="kh-rail-in"><input type="text" placeholder="Claude 에게 물어보기…" disabled><button type="button" disabled>보내기</button></div>`;

  document.body.append(panel, bar, fab);
  document.body.classList.add('has-kh-rail');
  const ic = bar.querySelector('.kh-rail-ic');
  let open = load();

  function apply() {
    panel.hidden = !open;
    fab.hidden = open;
    ic.classList.toggle('is-on', open);
    if (open) panel.querySelector('.kh-rail-now').textContent = context();
    const css = getComputedStyle(root);
    const w = wide.matches
      ? (parseFloat(css.getPropertyValue('--kh-rail-bar')) || 0) + (open ? parseFloat(css.getPropertyValue('--kh-rail-panel')) || 0 : 0)
      : 0;
    root.style.setProperty('--kh-rail-w', w + 'px');
  }
  function set(v) { open = v; save(v); apply(); }

  ic.addEventListener('click', () => set(!open));
  fab.addEventListener('click', () => set(true));
  panel.querySelector('.kh-rail-x').addEventListener('click', () => set(false));
  wide.addEventListener('change', apply);
  apply();
}
