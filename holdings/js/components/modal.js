/* 공용 모달 껍데기.
 *
 * 무엇을 담을지는 부르는 쪽이 정하고, 이 파일은 **띄우고 닫는 것만** 맡는다.
 * 종목 모달이 첫 손님이지만 공시·뉴스도 같은 것을 쓰게 될 것이라 한 곳에 뒀다.
 * 두 번째 자리에서 또 만들면 닫는 방법·겹치는 순서가 제각각이 된다.
 *
 * 닫는 길을 넷 둔다 — 닫기 단추 · 바깥 누르기 · Esc · 뒤로가기.
 * 하나만 두면 "어떻게 닫지" 를 찾게 된다.
 *
 * ── 옆 서랍 ──
 *
 * 양옆 가장자리에 손잡이를 달 수 있다. 누르면 **모달이 그쪽으로 넓어지면서**
 * 칸이 하나 나온다 (2026-09-16 지시). 가운데를 좁히지 않는다 — 차트가
 * 줄어들면 서랍을 여는 값이 없다.
 *
 * 펼친 상태는 기억한다. 종목을 바꿀 때마다 다시 펼치게 하지 않는다.
 */

/* 지금 떠 있는 모달. 한 번에 하나만 띄운다 — 모달 위에 모달이 쌓이면
   Esc 를 눌렀을 때 어느 것이 닫히는지 알 수 없다. */
let current = null;

/* 펼친 상태를 적어 두는 곳. 이 브라우저에만 남는다. */
const REMEMBER_KEY = 'kh-drawer:';

function remembered(key) {
  try { return localStorage.getItem(REMEMBER_KEY + key) === 'on'; }
  catch { return false; }        // 사생활 보호 창에서는 못 읽는다. 접힌 채로 간다
}

function remember(key, on) {
  try { localStorage.setItem(REMEMBER_KEY + key, on ? 'on' : 'off'); }
  catch { /* 못 적어도 이번 판에는 열려 있다 */ }
}

/**
 * @param {object}   opts
 * @param {string}   opts.label    읽어주는 이름 (화면에는 안 보인다)
 * @param {object}   [opts.drawers] { left: {key, label}, right: {key, label} }
 * @param {Function} [opts.onToggle] 서랍을 여닫을 때. 차트 크기를 다시 잡는 자리
 * @param {Function} [opts.onClose]  닫힐 때. 스스로 도는 것을 여기서 멈춘다
 * @returns {{ body: HTMLElement, close: Function }}
 */
export function openModal({ label = '', drawers = null, onToggle, onClose } = {}) {
  if (current) current.close();

  /* 손잡이와 모달을 한 판(stage) 에 올린다.
     서랍을 펼칠 때 미는 것은 이 판이다 — 모달만 밀면 손잡이가 제자리에
     남아 어긋난다 (2026-09-16 에 그렇게 나왔다). */
  /* 셋으로 나눈다.
   *
   *     .kh-stage         서랍을 펼칠 때 미는 판. 여기에 transform 이 걸린다
   *     .kh-modal         흰 창. 손잡이는 이 안 가장자리에 붙는다
   *     .kh-modal-scroll  실제로 굴러가는 칸
   *
   * 손잡이를 창 안에 두면서 굴러가지 않게 하려면 이 층이 필요하다.
   * 스크롤되는 요소 안에 절대 위치를 두면 내용과 함께 밀려 올라간다.
   */
  const veil = document.createElement('div');
  veil.className = 'kh-veil';
  veil.innerHTML = `<div class="kh-stage">
      <div class="kh-modal" role="dialog" aria-modal="true"
           aria-label="${label}" tabindex="-1">
        <div class="kh-modal-scroll"></div>
      </div>
    </div>`;
  const stage = veil.querySelector('.kh-stage');
  const shell = veil.querySelector('.kh-modal');
  const body = veil.querySelector('.kh-modal-scroll');

  /* ── 옆 서랍 손잡이 ──
     모달과 형제로 둔다. 모달이 넓어지면 손잡이가 자연스럽게 밀려난다. */
  const tabs = {};
  if (drawers) {
    for (const side of ['left', 'right']) {
      const d = drawers[side];
      if (!d) continue;
      /* 화살표만 둔다 — 무엇이 들었는지는 적지 않는다 (2026-09-16 지시).
         이름은 읽어주는 쪽에만 남긴다. */
      const tab = document.createElement('button');
      tab.className = `kh-drawer-tab is-${side}`;
      tab.type = 'button';
      tab.title = d.label;
      tab.setAttribute('aria-label', d.label);
      tab.innerHTML = '<span class="kh-drawer-arrow"></span>';
      tab.addEventListener('click', () => toggle(side));
      tabs[side] = tab;
      shell.appendChild(tab);       /* 창 안 가장자리. 자리는 CSS 가 잡는다 */

      if (remembered(d.key)) setOpen(side, true, { quiet: true });
    }
  }

  function isDrawerOpen(side) {
    return stage.classList.contains('has-' + side);
  }

  function setOpen(side, on, { quiet = false } = {}) {
    stage.classList.toggle('has-' + side, on);
    const tab = tabs[side];
    if (tab) {
      tab.classList.toggle('is-open', on);
      tab.setAttribute('aria-expanded', on ? 'true' : 'false');
    }
    if (drawers && drawers[side]) remember(drawers[side].key, on);
    if (!quiet && onToggle) onToggle(side, on);
  }

  function toggle(side) {
    setOpen(side, !isDrawerOpen(side));
  }

  document.body.appendChild(veil);

  /* 뒤 화면이 같이 굴러가면 어디를 보고 있었는지 잃는다 */
  const scrollY = window.scrollY;
  document.body.style.overflow = 'hidden';

  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    current = null;
    document.removeEventListener('keydown', onKey);
    document.body.style.overflow = '';
    window.scrollTo(0, scrollY);
    veil.remove();
    if (onClose) onClose();
  }

  /* Esc 는 **서랍부터** 닫는다. 서랍을 열어 둔 채 Esc 를 누르면 모달이
     통째로 사라져서, 보던 것을 되찾으려면 다시 종목을 눌러야 한다. */
  function onKey(e) {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    for (const side of ['right', 'left']) {
      if (isDrawerOpen(side)) { setOpen(side, false); return; }
    }
    close();
  }

  /* 안쪽을 눌렀을 때는 닫지 않는다. 글자를 끌어 선택하다 바깥에서 손을
     떼는 일이 있어서, 누르기 시작한 곳이 바깥일 때만 닫는다. */
  let startedOutside = false;
  veil.addEventListener('mousedown', e => { startedOutside = e.target === veil; });
  veil.addEventListener('click', e => { if (e.target === veil && startedOutside) close(); });

  document.addEventListener('keydown', onKey);
  shell.focus();

  /* 서랍을 펼쳐 둔 채로 열면, 첫 그림에서 이미 밀려 있어야 한다.
     처음부터 transition 이 걸려 있으면 가운데에서 옆으로 스르륵 움직이는
     것이 보인다 (2026-09-16 지적). 한 판 그린 뒤에 켠다. */
  requestAnimationFrame(() => stage.classList.add('is-ready'));

  current = { close };
  return { body, close, toggle, isDrawerOpen };
}

/** 지금 떠 있는 모달이 있으면 닫는다. 없으면 아무 일도 하지 않는다. */
export function closeModal() {
  if (current) current.close();
}

/** 지금 무엇인가 떠 있나. */
export function isOpen() {
  return current != null;
}
