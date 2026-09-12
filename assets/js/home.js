/* ==========================================================================
   KJC Studio · home.js
   data/categories.json 을 읽어서 메인 페이지의 카테고리 목록을 렌더링

   갤러리는 여기서 그리지 않는다. 메인은 입구 역할만 하고,
   작업물은 category/*.html 에서 gallery.js 가 그린다.
   ========================================================================== */

(function () {
  "use strict";

  function basePath() {
    // main.js · gallery.js 와 같은 로직
    const override = document.body?.dataset?.siteRoot;
    if (override !== undefined) return override;
    const path = window.location.pathname;
    const segs = path.split("/").filter(Boolean);
    const isFile = segs.length > 0 && /\.[a-z0-9]+$/i.test(segs[segs.length - 1]);
    const dirDepth = isFile ? segs.length - 1 : segs.length;
    return "../".repeat(dirDepth);
  }

  /** order 1 → "01". 순서가 없으면 목록에서의 자리로 매긴다. */
  function numberOf(cat, index) {
    const n = cat.order || index + 1;
    return String(n).padStart(2, "0");
  }

  function renderItem(cat, index, base) {
    const a = document.createElement("a");
    a.className = "cat-item";
    a.href = `${base}category/${cat.id}.html`;
    a.dataset.id = cat.id;

    a.innerHTML = `
      <span class="cat-num">${numberOf(cat, index)}</span>
      <span class="cat-body">
        <span class="cat-name">${cat.label || cat.id}<span class="dot">.</span></span>
        <span class="cat-desc">${cat.description || ""}</span>
      </span>
      <span class="cat-arrow" aria-hidden="true"></span>
    `;
    return a;
  }

  async function init() {
    const container = document.querySelector(".cat-list");
    if (!container) return;

    const base = basePath();
    let doc;
    try {
      const res = await fetch(base + "data/categories.json");
      if (!res.ok) throw new Error(`fetch failed: ${res.status}`);
      doc = await res.json();
    } catch (err) {
      console.error("[home] categories 불러오기 실패", err);
      container.innerHTML = `
        <div class="cat-empty">
          <strong>Error.</strong>
          <p>카테고리 목록을 불러오지 못했습니다.</p>
        </div>`;
      return;
    }

    const list = (doc.list || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
    if (!list.length) {
      container.innerHTML = `
        <div class="cat-empty">
          <strong>Coming soon.</strong>
          <p>카테고리가 아직 없습니다. <code>data/categories.json</code> 에 추가하세요.</p>
        </div>`;
      return;
    }

    const frag = document.createDocumentFragment();
    list.forEach((cat, i) => frag.appendChild(renderItem(cat, i, base)));
    container.innerHTML = "";
    container.appendChild(frag);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
