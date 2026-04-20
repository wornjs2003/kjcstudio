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

    if (works.length === 0) {
      renderEmpty(container, catMeta?.label || activeId);
      return;
    }

    const frag = document.createDocumentFragment();
    works.forEach((w) => frag.appendChild(renderItem(w)));
    container.innerHTML = "";
    container.appendChild(frag);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
