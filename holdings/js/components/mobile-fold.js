/* 모바일 칸 접기 (2026-09-22 지시)

   재권님 말씀 그대로다.

     「모바일에서는 홀딩스에 칸별로 접기 버튼이 있어야 할거같은데
      접기누르면 제목만 보이게 되도록」

   **PC 는 안 건드린다.** 700px 을 넘으면 단추를 떼고 접힘도 전부 푼다 —
   좁혔다 넓혔다 해도 넓은 화면은 늘 지금 모습이다.

   **접는 것은 CSS 가 한다.** 칸에 `.is-fold` 하나를 붙이면 제목 줄과 이
   단추만 남고 나머지 자식이 사라진다(`home.css` 의 폰 블록).
   여기서는 단추를 붙이고 그 클래스를 켜고 끄는 일만 한다 —
   높이를 재서 JS 로 주무르지 않는다. 그러면 칸마다 값이 생긴다.

   **「보는 것을 바꿔도 자리는 그대로다」 와 부딪히지 않는다.**
   그 룰이 이미 가르고 있다 — 「열거나 접으려고 눌렀다」 는 **늘거나 주는
   것이 맞다**. 누른 사람이 시킨 일이다. 「갈아 끼우기」 가 아니다. */

const MQ = window.matchMedia('(max-width: 700px)');
const KEY = 'kh.fold.v1';

/* [칸, 제목 줄, 기억할 이름]

   제목 줄은 **칸의 첫 자식**이다 — 여섯 칸 모두 그렇다 (2026-09-22 실측).
   그래도 선택자로 적는다. 첫 자식에 기대면 위에 무엇이 하나 끼는 순간
   **제목이 같이 접힌다.** */
const LIST = [
  ['.kh-idx-main',                    ':scope > .kh-idx-head', 'chart'],
  ['.kh-idxp .kh-p3-s:nth-child(1)',  ':scope > .kh-p3-h',     'inv'],
  ['.kh-idxp .kh-p3-s:nth-child(2)',  ':scope > .kh-p3-h',     'ai'],
  ['.kh-idxp .kh-p3-s:nth-child(3)',  ':scope > .kh-p3-h',     'news'],
  ['.kh-rank-card',                   ':scope > .kh-tabs',     'rank'],
  ['.kh-dc-card',                     ':scope > .kh-sched-h',  'disc'],
  ['.kh-sc-card',                     ':scope > .kh-tabs',     'sector'],
  ['.kh-rank > .kh-card:last-child',  ':scope > .kh-tabs',     'daily'],
];

/* 접어 둔 칸을 기억한다. **처음에는 전부 펴진 채**다 — 안 누르면
   지금 화면과 똑같아야 한다. */
function read() {
  try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); }
  catch { return new Set(); }          /* 사파리 사생활 모드에서 던진다 */
}
function write(set) {
  try { localStorage.setItem(KEY, JSON.stringify([...set])); } catch { /* 못 써도 접기는 된다 */ }
}

function button(name, on) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'kh-foldbtn';
  b.dataset.fold = name;
  b.setAttribute('aria-expanded', on ? 'false' : 'true');
  /* 글자가 아니라 꺾쇠다. 접히면 오른쪽(▸), 펴지면 아래(▾) */
  b.textContent = on ? '▸' : '▾';
  b.title = on ? '펴기' : '접기';
  b.setAttribute('aria-label', b.title);
  return b;
}

function mount() {
  const folded = read();
  for (const [box, head, name] of LIST) {
    const el = document.querySelector(box);
    if (!el) continue;                       /* 아직 안 그려진 칸은 다음에 잡는다 */
    const h = el.querySelector(head);
    if (!h) continue;
    h.classList.add('kh-fold-h');
    if (el.querySelector(':scope > .kh-foldbtn')) continue;   /* 이미 붙였다 */
    const on = folded.has(name);
    el.classList.toggle('is-fold', on);
    el.appendChild(button(name, on));
  }
}

function unmount() {
  document.querySelectorAll('.kh-foldbtn').forEach((b) => b.remove());
  document.querySelectorAll('.is-fold').forEach((e) => e.classList.remove('is-fold'));
}

/* 단추는 다시 그려질 수 있으므로 **문서에 한 번만** 건다 */
function onClick(e) {
  const b = e.target.closest('.kh-foldbtn');
  if (!b) return;
  const el = b.parentElement;
  const name = b.dataset.fold;
  const on = !el.classList.contains('is-fold');
  el.classList.toggle('is-fold', on);
  b.textContent = on ? '▸' : '▾';
  b.title = on ? '펴기' : '접기';
  b.setAttribute('aria-label', b.title);
  b.setAttribute('aria-expanded', on ? 'false' : 'true');
  const folded = read();
  folded[on ? 'add' : 'delete'](name);
  write(folded);
}

export function mountMobileFold() {
  document.addEventListener('click', onClick);
  const sync = () => (MQ.matches ? mount() : unmount());
  MQ.addEventListener('change', sync);
  sync();
  /* 패널 셋과 순위표는 값이 온 뒤에 다시 그려진다. 그때 단추가 날아가므로
     **칸이 바뀌면 다시 붙인다.** 이미 있으면 `mount()` 가 건너뛴다. */
  const app = document.querySelector('.kh-app');
  if (!app) return;
  /* 시세가 들어올 때마다 칸이 다시 그려진다. 그때마다 바로 돌면 1초에도
     여러 번이라, **다음 그림 한 번으로 모은다.** */
  let waiting = false;
  new MutationObserver(() => {
    if (waiting || !MQ.matches) return;
    waiting = true;
    requestAnimationFrame(() => { waiting = false; mount(); });
  }).observe(app, { childList: true, subtree: true });
}
