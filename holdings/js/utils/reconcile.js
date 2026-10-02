/* ==========================================================================
   목록을 **끼워 넣는다** — 통째로 다시 그리지 않는다 (2026-10-02)

   `host.innerHTML = rows.map(html).join('')` 는 줄 하나가 더해졌을 때도
   **있던 줄을 다 버리고 다시 만든다.** 그래서 셋이 함께 망가진다.

       굴려 둔 자리   굴러가는 칸이 새 노드가 되면 **맨 위로 돌아간다**
       누르던 자리    `:focus` 와 글자 선택이 풀린다
       만드는 비용    바뀐 것이 한 줄인데 백 개를 만든다

   **값이 아니라 노드를 아낀다.** 2026-10-02 실측(지금 뜨는 산업) — 갱신 한
   바퀴에 통째로 다시 그리면 요소 221개를 만들고, 끼워 넣으면 **1줄(5개)** 이다.

   ⚠️ **「DOM 변경 건수」 로 재면 오히려 늘어 보인다.** 줄을 옮기는 것이
   기록으로는 추가+삭제로 세어져서다 — **잣대는 「만든 요소 수」** 다.

   ── 쓰는 곳 ──

   뉴스 · 공시 · 산업 종목 줄처럼 **같은 이름으로 다시 오는 목록**이다.
   이름(`key`)은 그 줄을 가리키는 것이어야 한다 — 링크 · 종목코드 · 접수번호.
   **순서나 식구가 바뀌는 것은 막지 않는다.** 있던 줄은 옮겨 쓴다.
   ========================================================================== */

/**
 * @param {Element} host   줄이 들어가는 칸
 * @param {Array}   items  그릴 것
 * @param {object}  opt
 * @param {Function} opt.key    항목 → 그 줄 이름 (문자열)
 * @param {Function} opt.html   항목 → 줄 HTML. **처음 그릴 때와 같은 것을 쓴다**
 * @param {Function} [opt.patch] (줄, 항목) → 값만 고친다.
 *        없으면 **모양이 달라진 줄만** 새로 만든다 (앞뒤 줄은 그대로 남는다)
 * @param {string}  [opt.attr='k']  줄 이름을 담는 `data-` 이름.
 *        줄 HTML 이 이미 이름을 들고 있으면(`data-code`) 그것을 쓴다
 */
export function patchRows(host, items, { key, html, patch, attr = 'k' } = {}) {
  if (!host) return;
  const have = new Map();
  for (const el of Array.from(host.children)) {
    const k = el.dataset ? el.dataset[attr] : null;
    /* 이름이 없는 것은 「불러오는 중」·「없습니다」 같은 **딴 것**이다.
       그대로 두면 목록 위에 남으므로 지운다. **이름이 겹친 줄**도 지운다 —
       맵에 하나만 남아 나머지가 제자리에 고아로 남는다. */
    if (k == null || have.has(k)) el.remove(); else have.set(k, el);
  }

  let prev = null;
  for (const it of items) {
    const k = String(key(it));
    const h = html(it);
    let el = have.get(k);
    if (el) {
      have.delete(k);
      if (patch) patch(el, it);
      else if (el.__h !== h) {          // 모양이 달라졌다 — 그 줄만 다시 만든다
        const next = make(h, k, attr);
        el.replaceWith(next);
        el = next;
      }
    } else {
      el = make(h, k, attr);
    }
    el.__h = h;
    /* **제자리면 건드리지 않는다** — 옮기는 것도 DOM 변경이다 */
    const atRight = prev ? prev.nextElementSibling === el : host.firstElementChild === el;
    if (!atRight) { if (prev) prev.after(el); else host.prepend(el); }
    prev = el;
  }
  have.forEach((el) => el.remove());    // 목록에서 빠진 줄
}

function make(h, k, attr) {
  const t = document.createElement('div');
  t.innerHTML = h;
  const el = t.firstElementChild;
  /* 줄 HTML 은 **뿌리 요소 하나**여야 한다. 둘이면 뒤엣것을 잃고,
     없으면 아래에서 터진다 — 조용히 줄이 빠지는 것보다 여기서 멈춘다 */
  if (!el || t.childElementCount !== 1) throw new Error(`patchRows: 줄 HTML 은 요소 하나여야 합니다 (${k})`);
  el.dataset[attr] = k;
  return el;
}
