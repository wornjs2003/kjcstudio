/* 종목 아이콘 — 있으면 그림, 없으면 회사색 바탕에 이름 두 글자.
 *
 * 네 자리가 같은 모양을 그린다 — 관심 사이드바 · 종목 목록 · 미리보기 머리 ·
 * 종목 화면 머리. 네 곳에 같은 코드를 두지 않으려고 여기 모았다
 * (CLAUDE.md 「같은 값은 한 곳에만 둔다」).
 *
 * ── 왜 목록을 먼저 읽나 ──
 *
 * 그림이 없는 종목이 130개쯤 있다 (우선주가 대부분). 목록 없이 <img> 를 넣고
 * 실패하면 지우는 방식은 콘솔에 404(그런 주소 없음)가 쌓인다. 미리 알고
 * 넣지 않으면 그럴 일이 없다.
 *
 * 목록은 34KB 이고 모듈을 읽는 순간 받기 시작한다. 화면이 첫 줄을 그리기 전에
 * `ready` 를 기다리면 글자가 그림으로 바뀌는 깜빡임도 없다.
 *
 * ── 배포본에서는 아직 안 보인다 ──
 *
 * 그림은 저장소에 담지 않는다 (uidata/README.md). 배포본에는 파일이 없으므로
 * 목록 읽기가 실패하고, 전부 회사색+글자로 나온다. 실패해도 화면은 멀쩡하다.
 */

/* 서버가 저장소 루트를 내보내므로 두 화면(/holdings/index.html ·
 * /holdings/stock.html) 어디서 열어도 이 경로가 맞는다. */
const ICON_BASE = '/uidata/icons/';
const LIST_URL = ICON_BASE + 'index.json';

/* 그림이 있는 종목코드. 아직 못 읽었으면 빈 집합이라 전부 글자로 나온다. */
let have = new Set();

/* 목록 읽기. 모듈을 읽는 순간 시작하므로 화면이 그려질 때쯤이면 대개 와 있다.
 *
 * 늦게 오더라도 화면이 순서를 신경 쓸 필요는 없다. 도착하면 이미 그려진 칸을
 * 찾아 스스로 채운다. 그래서 각 화면은 이것을 기다리지 않아도 된다. */
export const ready = fetch(LIST_URL, { cache: 'default' })
  .then(r => (r.ok ? r.json() : null))
  .then(d => { have = new Set((d && d.icons) || []); fillDrawn(); })
  .catch(() => { /* 그림이 없는 기계다. 글자로 간다 */ });

/** 목록보다 먼저 그려진 칸을 뒤늦게 채운다. */
function fillDrawn() {
  if (!have.size) return;
  document.querySelectorAll('.kh-ic[data-code]').forEach(el => {
    const code = el.dataset.code;
    if (have.has(code) && !el.querySelector('.kh-ic-img')) {
      el.insertAdjacentHTML('afterbegin', imgTag(code));
    }
  });
}

/** 이 종목에 그림이 있나. */
export function hasIcon(code) {
  return have.has(code);
}

function brandOf(s) {
  return (s && s.brand) || 'var(--kh-bg-active)';
}

function labelOf(s) {
  return ((s && s.name) || '').slice(0, 2);
}

function imgTag(code) {
  return have.has(code)
    ? `<img class="kh-ic-img" src="${ICON_BASE}${code}.png" alt="" loading="lazy">`
    : '';
}

/** 줄을 문자열로 만드는 자리용. `extra` 는 덧붙일 클래스.
 *
 * `data-code` 를 붙이는 이유는 위 fillDrawn 이 나중에 찾아야 해서다. */
export function iconHtml(s, extra = '') {
  const cls = extra ? `kh-ic ${extra}` : 'kh-ic';
  return `<span class="${cls}" data-code="${s.code}" style="background:${brandOf(s)}"`
       + `>${imgTag(s.code)}${labelOf(s)}</span>`;
}

/** 이미 있는 칸을 칠하는 자리용.
 *
 * 시세가 갱신될 때마다 불리는 자리가 있다. 같은 종목이면 손대지 않는다 —
 * 매번 innerHTML 을 새로 쓰면 그림이 다시 그려져 미세하게 깜빡인다. */
export function paintIcon(el, s) {
  if (!el || !s) return;
  if (el.dataset.code === s.code && (!have.has(s.code) || el.querySelector('.kh-ic-img'))) return;
  el.dataset.code = s.code;
  el.style.background = brandOf(s);
  el.innerHTML = `${imgTag(s.code)}${labelOf(s)}`;
}
