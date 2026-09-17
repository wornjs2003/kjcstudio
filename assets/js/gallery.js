/* ==========================================================================
   KJC Studio · gallery.js
   data/works.json + data/categories.json 을 읽어서 매저너리 갤러리 렌더링
   ========================================================================== */

(function () {
  "use strict";

  function basePath() {
    // main.js 가 쓰던 로직과 동일한 간단 버전
    const override = document.body?.dataset?.siteRoot;
    if (override !== undefined) return override;
    const path = window.location.pathname;
    const segs = path.split("/").filter(Boolean);
    const isFile = segs.length > 0 && /\.[a-z0-9]+$/i.test(segs[segs.length - 1]);
    const dirDepth = isFile ? segs.length - 1 : segs.length;
    return "../".repeat(dirDepth);
  }

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`fetch failed: ${url}`);
    return res.json();
  }

  /**
   * span 힌트 → 플레이스홀더 비율 매핑
   * Yanggang 레퍼런스처럼 들쭉날쭉한 높이 연출용.
   */
  function placeholderRatio(span) {
    switch (span) {
      case "tall":   return "3 / 5";
      case "large":  return "4 / 5";
      case "wide":   return "5 / 3";
      case "square": return "1 / 1";
      default:       return "4 / 5";
    }
  }

  function renderItem(work) {
    const item = document.createElement("article");
    item.className = "gallery-item";
    item.dataset.id = work.id;

    const media = document.createElement("div");
    media.className = "gallery-item-media";

    if (work.thumbnail) {
      const img = document.createElement("img");
      img.src = work.thumbnail;
      img.alt = work.title || "";
      img.loading = "lazy";
      media.appendChild(img);
    } else {
      const ph = document.createElement("div");
      ph.className = "gallery-item-placeholder";
      ph.style.setProperty("--ph-ratio", placeholderRatio(work.span));
      ph.innerHTML = `<span>${work.title || "Untitled"}</span>`;
      media.appendChild(ph);
    }

    const info = document.createElement("div");
    info.className = "gallery-item-info";
    info.innerHTML = `
      <div class="gallery-item-title">${work.title || "Untitled"}</div>
      <div class="gallery-item-meta">${work.year || ""}${work.client ? " · " + work.client : ""}</div>
    `;

    item.appendChild(media);
    item.appendChild(info);

    // 클릭 → 라이트박스 (썸네일 있는 경우)
    if (work.thumbnail) {
      item.addEventListener("click", () => openLightbox(work));
    }

    return item;
  }

  function openLightbox(work) {
    let box = document.querySelector(".lightbox");
    if (!box) {
      box = document.createElement("div");
      box.className = "lightbox";
      box.innerHTML = `
        <button class="lightbox-close" aria-label="닫기">×</button>
        <img alt="" />
        <div class="lightbox-caption"></div>
      `;
      document.body.appendChild(box);

      box.addEventListener("click", (e) => {
        if (e.target === box || e.target.classList.contains("lightbox-close")) {
          box.classList.remove("open");
        }
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") box.classList.remove("open");
      });
    }

    const img = box.querySelector("img");
    const cap = box.querySelector(".lightbox-caption");
    img.src = work.thumbnail;
    img.alt = work.title || "";
    cap.innerHTML = `<strong>${work.title || ""}</strong><span>${work.year || ""}${work.client ? " · " + work.client : ""}</span>`;
    box.classList.add("open");
  }

  /* ── 갈래 탭 ──────────────────────────────
     카테고리 아래에 갈래를 더 두고 싶을 때 쓴다. categories.json 의 그 항목에
     groups 를 적으면 탭이 생기고, 없으면 지금까지대로 갤러리 하나만 나온다.
     그래서 다른 카테고리는 이 코드가 있어도 달라지는 것이 없다.

     AI Work 가 첫 사례다 — 컨셉 · 캐릭터 · 애니메이션 · 배경은 만드는 방식과
     보는 눈이 서로 달라서 한 판에 섞으면 읽히지 않는다 (2026-09-17 지시). */

  function renderGroupTabs(host, groups, works, onPick) {
    const counts = {};
    works.forEach((w) => {
      const g = w.group || "";
      if (g) counts[g] = (counts[g] || 0) + 1;
    });

    const all = [{ id: "", label: "전체" }].concat(groups);
    host.innerHTML = "";

    all.forEach((g, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "group-tab" + (i === 0 ? " is-on" : "");
      b.dataset.group = g.id;

      const n = g.id ? (counts[g.id] || 0) : works.length;
      b.innerHTML = `<span>${g.label}</span><i>${n}</i>`;
      /* 아직 한 점도 없는 갈래는 눌러도 빈 화면이라, 눌리지만 흐리게 둔다.
         숨기지 않는 것은 「앞으로 여기에 무엇이 올라오는지」 가 보여야 해서다. */
      if (n === 0) b.classList.add("is-empty");

      b.addEventListener("click", () => {
        host.querySelectorAll(".group-tab").forEach((x) => x.classList.remove("is-on"));
        b.classList.add("is-on");
        onPick(g.id, g);
      });
      host.appendChild(b);
    });
  }

  function renderEmpty(container, label) {
    container.innerHTML = `
      <div class="gallery-empty">
        <strong>Coming soon.</strong>
        <p>${label} 카테고리 작업물이 곧 채워집니다.</p>
      </div>
    `;
  }

  async function init() {
    const category = document.body.dataset.category;
    const titleEl = document.querySelector(".category-title");
    const descEl = document.querySelector(".category-desc");
    const kickerEl = document.querySelector(".category-kicker");
    const container = document.querySelector(".gallery");

    if (!container) return;

    let categoriesDoc, worksDoc;
    try {
      const base = basePath();
      [categoriesDoc, worksDoc] = await Promise.all([
        fetchJSON(base + "data/categories.json"),
        fetchJSON(base + "data/works.json"),
      ]);
    } catch (err) {
      console.error("[gallery] data load fail", err);
      container.innerHTML = `<div class="gallery-empty"><strong>Error.</strong><p>데이터를 불러오지 못했습니다.</p></div>`;
      return;
    }

    // 메인페이지(index.html) 는 body.dataset.category 가 없으면 featured 사용
    const activeId = category || categoriesDoc.featured;
    const catMeta = (categoriesDoc.list || []).find((c) => c.id === activeId);

    if (titleEl && catMeta) {
      titleEl.innerHTML = `${catMeta.label}<span class="dot">.</span>`;
    }
    if (kickerEl && catMeta?.kicker) {
      kickerEl.textContent = catMeta.kicker;
    }
    if (descEl && catMeta?.description) {
      descEl.textContent = catMeta.description;
    }

    const works = (worksDoc.works || [])
      .filter((w) => w.category === activeId)
      .sort((a, b) => (a.order || 0) - (b.order || 0));

    /* 갈래를 정해 둔 카테고리면 탭을 먼저 그린다 */
    const groups = catMeta?.groups || [];
    const tabHost = document.querySelector(".group-tabs");

    function draw(groupId, groupMeta) {
      const list = groupId ? works.filter((w) => w.group === groupId) : works;
      if (descEl) {
        descEl.textContent = (groupMeta && groupMeta.description)
          || catMeta?.description || "";
      }
      if (list.length === 0) {
        renderEmpty(container, (groupMeta && groupMeta.label) || catMeta?.label || activeId);
        return;
      }
      const frag = document.createDocumentFragment();
      list.forEach((w) => frag.appendChild(renderItem(w)));
      container.innerHTML = "";
      container.appendChild(frag);
    }

    if (groups.length && tabHost) {
      tabHost.hidden = false;
      renderGroupTabs(tabHost, groups, works, draw);
    }
    draw("", null);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
