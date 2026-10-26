/* 종목 풍선 — 종목 이름에 마우스를 올리면 섹터 · 주요 매출원 (2026-10-26 재권님 「실시간 순위나 차트 종목 이름위에 마우스
 * 올리면 해당 종목의 섹터나 주요매출원을 보고싶은데」 → 출처 「(다) 둘 다」 · 작업우선순위 경유).
 *
 *   값      서버 /api/dart/profile?code= 하나(server/company_profile.py) — 네이버(FnGuide) 기업개요 + DART 정기보고서 매출 표.
 *           화면은 셈하지 않고 받은 것을 그대로 보인다. 받은 값은 이 탭에서만 들고 있는다(언제 다시 받을지는 서버가 정한다)
 *   자리    이름 글자에 `data-co="<종목코드>"` 를 단다 — 순위 표 · 「자세히」 모달 표 · 큰 차트 머리 · 종목 모달 제목.
 *           풍선은 document 에 한 번만 건다(나중에 그린 칸도 그대로 걸린다)
 *   모양    공용 용어 풍선(assets/css/glossary.css 의 .gl-tip · .gl-h · .gl-short · .gl-kv · .gl-src)을 그대로 쓴다 — 세 번째 풍선
 *           모양을 만들지 않는다. 그 파일은 용어집 코드(assets/js/glossary.js)가 걸어 두므로 여기서는 없을 때만 건다.
 *           **자리만 다르다** — 순위 표는 스크롤 칸 안이라 칸 안에 붙이면 잘린다. 그래서 body 에 붙이고 화면 좌표(fixed)로 둔다.
 *           칸 크기를 안 건드린다(「보는 것을 바꿔도 자리는 그대로다」)
 *   터치    짧게 누르면 지금처럼 줄 고르기 · **길게 누르면** 풍선(그때 뒤따르는 누르기는 삼킨다) · 다른 곳을 누르면 닫힘
 */
import { apiFetch } from '../data/api.js';

const CSS = '/assets/css/glossary.css';
/* 공용 풍선에 없는 두 가지만 여기 둔다 — 화면 좌표 자리(모달 z-index 200 보다 위) · 매출 표. 색은 토큰만 */
const OWN = `.kh-cotip{position:fixed;z-index:300;top:0;left:0}
.kh-cotip-t{width:100%;border-collapse:collapse;margin:2px 0 6px;font-size:.72rem;line-height:1.45;color:var(--text-primary)}
.kh-cotip-t td{padding:2px 4px;vertical-align:top;border-top:1px solid var(--kh-border)}
.kh-cotip-t tr:first-child td{color:var(--text-muted);border-top:0}`;
const LONG_MS = 450;                     // 길게 누르기로 보는 시간 — 그리기 시간이 아니라 손가락 판정이다
const got = new Map();                   // code -> 받은 값(또는 받는 중 Promise)
let tip = null, anchor = null, swallowClick = false;

const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function load(code) {
  if (!got.has(code)) {
    got.set(code, apiFetch(`/api/dart/profile?code=${code}`)
      .then((r) => (r && r.ok ? r.json() : null))
      .then((j) => { const v = j && j.ok ? j.data : { error: '받지 못했습니다' }; got.set(code, v); return v; })
      .catch(() => { got.delete(code); return { error: '받지 못했습니다' }; }));
  }
  return Promise.resolve(got.get(code));
}

const ymd = (s) => (s && s.length === 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6)}` : s || '');

function html(name, d) {
  if (!d) return `<b class="gl-h">${esc(name)}</b><p class="gl-short">불러오는 중</p>`;
  if (d.error) return `<b class="gl-h">${esc(name)}</b><p class="gl-short">${esc(d.error)}</p>`;
  const sec = [d.sector?.wics, d.sector?.krx].filter(Boolean);
  const kv = sec.length ? `<div class="gl-kv"><span>섹터</span><b>${esc(sec.join(' · '))}</b></div>` : '';
  const sum = (d.summary || []).length
    ? `<p class="gl-short">${d.summary.map(esc).join('<br>')}</p>` : '';
  let tbl = '';
  if (d.products && d.products.rows?.length) {
    const rows = d.products.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('');
    tbl = `<div class="gl-kv"><span>매출 구성</span><span>${esc(d.products.unit || '')}${d.products.cut ? ' · 앞부분만' : ''}</span></div>
      <table class="kh-cotip-t">${rows}</table>`;
  }
  const src = [];
  if (sum || sec.length) src.push(`네이버 · FnGuide 기업개요`);
  if (tbl) src.push(`DART ${esc(d.productsReport || '정기보고서')}${d.productsDate ? ' · ' + ymd(d.productsDate) : ''}`);
  const none = !sum && !tbl && !sec.length ? `<p class="gl-short">섹터 · 매출 구성을 찾지 못했습니다(ETF · 리츠 등)</p>` : '';
  const miss = sum && !tbl && d.productsError ? `<p class="gl-src">매출 비중 — ${esc(d.productsError)}</p>` : '';
  return `<b class="gl-h">${esc(name)}</b>${kv}${sum}${tbl}${miss}${none}${src.length ? `<p class="gl-src">출처 ${src.join(' · ')}</p>` : ''}`;
}

function place() {
  if (!tip || !anchor) return;
  const a = anchor.getBoundingClientRect();
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let left = Math.min(a.left, window.innerWidth - 8 - w);
  left = Math.max(8, left);
  let top = a.bottom + 6;
  if (top + h > window.innerHeight - 8 && a.top - 6 - h > 8) top = a.top - 6 - h;
  tip.style.left = `${Math.round(left)}px`;
  tip.style.top = `${Math.round(top)}px`;
}

async function show(el) {
  const code = el.dataset.co;
  if (!/^\d{6}$/.test(code || '')) return;
  hide();
  anchor = el;
  tip = document.createElement('div');
  tip.className = 'gl-tip kh-cotip';
  tip.setAttribute('role', 'tooltip');
  const name = el.textContent.trim();
  const now = got.get(code);
  tip.innerHTML = html(name, now instanceof Promise ? null : now);
  document.body.appendChild(tip);
  place();
  const d = await load(code);
  if (anchor !== el || !tip) return;               // 그사이 다른 이름으로 옮겼다
  tip.innerHTML = html(name, d);
  place();
}

function hide() { if (tip) { tip.remove(); tip = null; } anchor = null; }

export function mountCompanyTip() {
  if (!document.querySelector(`link[href="${CSS}"]`)) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = CSS; document.head.appendChild(l);
  }
  const st = document.createElement('style'); st.textContent = OWN; document.head.appendChild(st);
  const fine = window.matchMedia('(hover: hover)').matches;
  document.addEventListener('mouseover', (e) => {
    if (!fine) return;
    if (anchor && !anchor.isConnected) hide();         // 표를 다시 그려 이름 칸이 바뀌었다 — mouseout 이 안 온다
    const el = e.target.closest('[data-co]');
    if (el && el !== anchor) show(el);
  });
  document.addEventListener('mouseout', (e) => {
    if (!fine || !anchor) return;
    const el = e.target.closest('[data-co]');
    if (el === anchor && !el.contains(e.relatedTarget)) hide();
  });
  /* 터치 — 길게 누르기 */
  let timer = null, startX = 0, startY = 0;
  document.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse') return;
    const el = e.target.closest('[data-co]');
    if (!el) { if (tip && !e.target.closest('.kh-cotip')) hide(); return; }
    startX = e.clientX; startY = e.clientY;
    clearTimeout(timer);
    timer = setTimeout(() => { swallowClick = true; show(el); }, LONG_MS);
  });
  const cancel = () => clearTimeout(timer);
  document.addEventListener('pointerup', cancel);
  document.addEventListener('pointercancel', cancel);
  document.addEventListener('pointermove', (e) => {
    if (Math.abs(e.clientX - startX) > 8 || Math.abs(e.clientY - startY) > 8) cancel();
  });
  document.addEventListener('click', (e) => {          // 길게 누른 뒤 따라오는 누르기는 줄 고르기로 안 넘긴다
    if (!swallowClick) return;
    swallowClick = false;
    e.stopPropagation(); e.preventDefault();
  }, true);
  document.addEventListener('contextmenu', (e) => { if (e.target.closest('[data-co]') && !fine) e.preventDefault(); });
  window.addEventListener('scroll', hide, true);       // 스크롤하면 자리가 어긋난다 — 닫는다
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
}
