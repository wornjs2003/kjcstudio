/* ==========================================================================
   KJC Holdings · h-page.js
   analysis, roadmap 등 신규 페이지의 partials nav/footer 주입 + active 처리
   (기존 dashboard main.js 와 별개)
   ========================================================================== */

(function () {
  "use strict";

  function basePath() {
    const override = document.body?.dataset?.siteRoot;
    if (override !== undefined) return override;
    const path = window.location.pathname;
    const segs = path.split("/").filter(Boolean);
    const isFile = segs.length > 0 && /\.[a-z0-9]+$/i.test(segs[segs.length - 1]);
    const dirDepth = isFile ? segs.length - 1 : segs.length;
    // holdings 가 루트인지 (독립 실행), 아니면 KJCStudio/holdings 인지 감지
    // holdings 내부 페이지 기준으로 상대 경로를 만든다.
    // - /holdings/analysis/ → ../ (holdings 루트로)
    // - /analysis/         → ../ (홀딩스가 루트인 경우)
    // 둘 다 마지막 디렉토리 depth가 1이면 "../", 0이면 ""
    // 좀 더 안정적으로 현재 경로에서 "holdings" 이후 segment 수로 계산
    const idx = segs.findIndex((s) => s === "holdings");
    if (idx >= 0) {
      const tail = isFile ? (segs.length - 1 - idx) - 1 : (segs.length - 1 - idx);
      return "../".repeat(Math.max(tail, 0));
    }
    // holdings 가 루트 (분리 배포된 상태)
    return "../".repeat(dirDepth);
  }

  async function injectPartial(mountId, partialPath, base) {
    const mount = document.getElementById(mountId);
    if (!mount) return;
    try {
      const res = await fetch(partialPath);
      if (!res.ok) throw new Error(`fetch failed: ${partialPath}`);
      const html = await res.text();
      mount.innerHTML = html.replaceAll("{{BASE}}", base);
    } catch (err) {
      console.warn("[h-page] partial 주입 실패", partialPath, err);
    }
  }

  function markActiveNav() {
    const current = document.body.dataset.nav;
    if (!current) return;
    document.querySelectorAll("[data-nav]").forEach((el) => {
      if (el.dataset.nav === current) el.classList.add("active");
    });
  }

  async function init() {
    const base = basePath();
    const partialsBase = base + "partials/";
    await Promise.all([
      injectPartial("h-nav", partialsBase + "nav.html", base),
      injectPartial("h-footer", partialsBase + "footer.html", base),
    ]);
    markActiveNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
