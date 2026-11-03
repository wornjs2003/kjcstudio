/* ==========================================================================
   오른쪽 Claude 줄 · 창 (2026-11-03 재권님 「화면 오른쪽에 항상 따라다니는 세로로 긴 창 하나도 추가해줘. 그창에 버튼을 누르면
   claude 와 연동되도록 개발 할거야」 → 「세로로 긴줄이 있고 아이콘을 눌렀을때 열리도록」 → 그림 넷 「응 맞아」)

   넓은 창 — 오른쪽 세로 줄(아이콘)이 늘 보이고, 누르면 창이 본문 위를 덮어 열린다(모달처럼 · 본문은 안 움직인다 ·
           재권님 「모달 창처럼 위를 덮는 방향으로」 11-03 — 밀면 폭 1000 에서 순위 칸이 창 밑으로 잘렸다) · Esc 로도 닫힌다.
   폰     — 오른쪽 아래 둥근 단추 · 누르면 창이 화면 전체.
   본문을 미는 폭은 html 의 --kh-rail-w 하나다(세로 줄만) — home.js 창 맞춤(fitScale)이 그 폭을 빼고 배율을 푼다.
   열림 · 닫힘은 이 브라우저에만 기억한다(보는 자리 기억 — 「화면이 가져도 되는 것」).

   연동(2026-11-03 재권님 「가로 해줘」) — 보내면 POST /api/claude/ask · 서버(server/claude_chat.py)가 맥미니 claude 를 한 번 부른다.
   답은 한 번에 온다(수십 초) · 그동안 「생각 중」. 한 번에 하나 — 돌고 있으면 서버가 429 로 돌려준다.
   보내는 것: 물음 · 보고 있는 것(종목 이름 · 코드 · 시장 지도) · 앞 대화. 시세 숫자는 서버가 붙인다.
   대화는 이 브라우저에만 남긴다(HIST_KEY · 최근 HIST_MAX 줄) — 서버는 저장하지 않는다.
   ========================================================================== */

const KEY = 'kh-claude-rail-open';
const WIDE = '(min-width: 768px)';
const ICON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z"/></svg>';
const QUICK = ['이 종목 요약', '오늘 시장 왜 빠졌나', '지금 뜨는 산업 설명'];
const HIST_KEY = 'kh-claude-chat';
const HIST_MAX = 40;
const ASK_URL = '/api/claude/ask';

function load() { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } }
function save(v) { try { localStorage.setItem(KEY, v ? '1' : '0'); } catch { /* 저장 못 해도 화면은 그대로 */ } }
function loadHist() {
  try { const a = JSON.parse(localStorage.getItem(HIST_KEY) || '[]'); return Array.isArray(a) ? a : []; } catch { return []; }
}
function saveHist(a) { try { localStorage.setItem(HIST_KEY, JSON.stringify(a.slice(-HIST_MAX))); } catch { /* 저장 못 해도 대화는 이 창에 남는다 */ } }

/* 「보고 있는 것」 — 첫 화면 큰 칸이 시장 지도면 그 이름, 아니면 큰 차트. 종목은 늘 함께 보낸다 —
   지도를 보는 중에도 「이 종목 요약」 이 그 아래 고른 종목(머리줄 #kh-idx-name — 종목 풍선이 쓰는 그 칸)을 가리키게 */
function context() {
  const hm = document.querySelector('.kh-hm:not([hidden]) .kh-hm-title');
  const nm = document.getElementById('kh-idx-name');
  const code = nm?.dataset.co || '';   // 코드가 붙기 전(「불러오는 중」)은 종목이 아니다
  return { screen: '홈', view: hm?.textContent.trim() || '큰 차트', name: code ? nm.textContent.trim() : '', code };
}
function contextLabel(c) {
  return `${c.screen} · ${c.view}` + (c.name ? ` · ${c.name}${c.code ? ` (${c.code})` : ''}` : '');
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
  panel.innerHTML = `<div class="kh-rail-hd"><b>Claude</b><span class="kh-rail-st">준비</span>
      <button type="button" class="kh-rail-clr" title="이 브라우저에 남은 대화를 지웁니다">대화 지우기</button>
      <button type="button" class="kh-rail-x" title="닫기" aria-label="닫기">×</button></div>
    <div class="kh-rail-ctx">보고 있는 것 — <b class="kh-rail-now"></b><br>보내면 이 화면과 서버가 받은 시세를 함께 보냅니다</div>
    <div class="kh-rail-body" aria-live="polite"></div>
    <div class="kh-rail-quick">${QUICK.map((q) => `<button type="button">${q}</button>`).join('')}</div>
    <div class="kh-rail-in"><input type="text" placeholder="Claude 에게 물어보기…" maxlength="2000"><button type="button">보내기</button></div>`;

  document.body.append(panel, bar, fab);
  document.body.classList.add('has-kh-rail');
  const ic = bar.querySelector('.kh-rail-ic');
  let open = load();

  function apply() {
    panel.hidden = !open;
    fab.hidden = open;
    ic.classList.toggle('is-on', open);
    if (open) panel.querySelector('.kh-rail-now').textContent = contextLabel(context());
    const css = getComputedStyle(root);
    const w = wide.matches ? parseFloat(css.getPropertyValue('--kh-rail-bar')) || 0 : 0;   // 열린 창은 덮으므로 폭에 안 넣는다
    root.style.setProperty('--kh-rail-w', w + 'px');
  }
  function set(v) { open = v; save(v); apply(); }

  /* ── 대화 ── */
  const body = panel.querySelector('.kh-rail-body');
  const st = panel.querySelector('.kh-rail-st');
  const input = panel.querySelector('.kh-rail-in input');
  const sendBtn = panel.querySelector('.kh-rail-in button');
  const quickBtns = [...panel.querySelectorAll('.kh-rail-quick button')];
  let hist = loadHist();
  let busy = false;

  function bubble(m) {
    const d = document.createElement('div');
    d.className = 'kh-rail-msg is-' + m.who;
    d.textContent = m.text;
    if (m.who === 'ai' && m.secs != null) {
      const s = document.createElement('small');
      s.textContent = `${m.secs}초`;
      d.append(s);
    }
    return d;
  }
  function paint(extra) {
    body.replaceChildren(...hist.map(bubble), ...(extra ? [bubble(extra)] : []));
    if (!hist.length && !extra) {
      const e = document.createElement('div');
      e.className = 'kh-rail-empty';
      e.textContent = '물어볼 것을 적거나 아래 단추를 눌러 주십시오. 답은 수십 초쯤 걸립니다.';
      body.append(e);
    }
    body.scrollTop = body.scrollHeight;
  }
  function setBusy(v) {
    busy = v;
    st.textContent = v ? '생각 중…' : '준비';
    st.classList.toggle('is-busy', v);
    [input, sendBtn, ...quickBtns].forEach((el) => { el.disabled = v; });
  }
  async function ask(q) {
    q = (q || '').trim();
    if (!q || busy) return;
    const ctx = context();
    panel.querySelector('.kh-rail-now').textContent = contextLabel(ctx);
    const prior = hist.filter((m) => m.who !== 'err');
    hist.push({ who: 'me', text: q });
    saveHist(hist);
    input.value = '';
    setBusy(true);
    paint({ who: 'wait', text: '생각 중… (보고 있는 것: ' + contextLabel(ctx) + ')' });
    try {
      const r = await fetch(ASK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, context: ctx, history: prior.map(({ who, text }) => ({ who, text })) }),
      });
      const j = await r.json().catch(() => null);
      if (!r.ok || !j?.ok) throw new Error(j?.error || `서버가 ${r.status} 를 냈습니다`);
      hist.push({ who: 'ai', text: j.data.text, secs: j.data.secs });
    } catch (e) {
      hist.push({ who: 'err', text: '못 받았습니다 — ' + (e?.message || e) });
    }
    saveHist(hist);
    setBusy(false);
    paint();
    input.focus();
  }
  sendBtn.addEventListener('click', () => ask(input.value));
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) ask(input.value); });
  quickBtns.forEach((b) => b.addEventListener('click', () => ask(b.textContent)));
  panel.querySelector('.kh-rail-clr').addEventListener('click', () => { if (busy) return; hist = []; saveHist(hist); paint(); });
  paint();

  ic.addEventListener('click', () => set(!open));
  fab.addEventListener('click', () => set(true));
  panel.querySelector('.kh-rail-x').addEventListener('click', () => set(false));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && open && !document.querySelector('.kh-veil')) set(false); });
  wide.addEventListener('change', apply);
  apply();
}
