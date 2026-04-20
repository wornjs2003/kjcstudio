/* ==========================================================================
   KJC Studio · main.js
   partials/nav.html + footer.html 동적 주입, active 메뉴 표시, More 패널
   ========================================================================== */

(function () {
  "use strict";

  /**
   * 현재 페이지에서 루트(KJCStudio)까지의 상대 경로를 구한다.
   * - / → ""
   * - /category/3d-modeling.html → "../"
   * - /about.html → ""
   */
  function computeBasePath() {
    const path = window.location.pathname;
    // "/foo/bar/index.html" 이면 세그먼트 중 파일명 빼고 개수 구함
    const segs = path.split("/").filter(Boolean);
    // 마지막 세그먼트가 .html 파일이면 디렉토리 아님
    const isFile = segs.length > 0 && /\.[a-z0-9]+$/i.test(segs[segs.length - 1]);
    const dirDepth = isFile ? segs.length - 1 : segs.length;

    // GitHub Pages 프로젝트 경로 (예: /kjcstudio/...) 를 깊이에서 제거
    // 여기선 단순하게 "현재 디렉토리가 루트면 '', category/ 면 '../'" 식으로만 처리
    // 단, 로컬 서버(포트 8080)에서는 루트가 KJCStudio이므로 dirDepth 그대로 사용
    const base = "../".repeat(dirDepth > 2 ? dirDepth - 1 : dirDepth);
    // 루트 index.html 을 "/" 로 서빙하는 경우, dirDepth=0 → base="" 이 맞다
    // category/ 하위(dirDepth=1) → base="../"
    // GitHub Pages 의 "/kjcstudio/..." 는 기본적으로 첫 세그먼트가 저장소명이므로
    // 별도 처리 원하면 data-site-root 속성을 body 에 두고 override
    const override = document.body?.dataset?.siteRoot;
    if (override !== undefined) return override;
    return base;
  }

  /**
   * partial 파일을 fetch 해서 placeholder {{BASE}} 치환 후 주입
   */
  async function injectPartial(mountId, partialPath, basePath) {
    const mount = document.getElementById(mountId);
    if (!mount) return;
    try {
      const res = await fetch(partialPath);
      if (!res.ok) throw new Error(`fetch failed: ${partialPath}`);
      const html = await res.text();
      mount.innerHTML = html.replaceAll("{{BASE}}", basePath);
    } catch (err) {
      console.warn("[partial] inject 실패", partialPath, err);
    }
  }

  /**
   * 현재 페이지에 해당하는 메뉴에 .active 붙이기
   * body 의 data-nav="..." 값을 사용
   */
  function markActiveNav() {
    const current = document.body.dataset.nav;
    if (!current) return;
    document.querySelectorAll("[data-nav]").forEach((el) => {
      if (el.dataset.nav === current) el.classList.add("active");
    });
  }

  /**
   * More 패널(⋯) 클릭 토글 (터치/키보드 지원)
   */
  function setupMoreMenu() {
    const more = document.querySelector(".nav-more");
    if (!more) return;
    const btn = more.querySelector(".nav-more-btn");
    if (!btn) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      more.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
      if (!more.contains(e.target)) more.classList.remove("open");
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") more.classList.remove("open");
    });
  }

  /**
   * 초기화
   */
  async function init() {
    const base = computeBasePath();
    const partialsBase = base + "partials/";

    await Promise.all([
      injectPartial("site-nav", partialsBase + "nav.html", base),
      injectPartial("site-footer", partialsBase + "footer.html", base),
    ]);

    markActiveNav();
    setupMoreMenu();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
