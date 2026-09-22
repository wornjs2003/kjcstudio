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
   * 모바일 햄버거 메뉴 토글
   * - 버튼(.nav-burger) ↔ 전체화면 패널(.nav-mobile)
   * - 열려 있는 동안 body 스크롤 잠금, 링크 클릭/ESC/리사이즈 시 닫힘
   */
  function setupMobileMenu() {
    const burger = document.querySelector(".nav-burger");
    const panel = document.querySelector(".nav-mobile");
    if (!burger || !panel) return;

    let isOpen = false;

    function open() {
      isOpen = true;
      panel.hidden = false;
      // hidden 해제 직후 클래스를 붙여야 페이드 트랜지션이 동작한다
      requestAnimationFrame(() => panel.classList.add("open"));
      burger.classList.add("open");
      burger.setAttribute("aria-expanded", "true");
      burger.setAttribute("aria-label", "메뉴 닫기");
      document.body.classList.add("nav-open");
    }

    function close() {
      isOpen = false;
      panel.classList.remove("open");
      burger.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
      burger.setAttribute("aria-label", "메뉴 열기");
      document.body.classList.remove("nav-open");
      // 페이드 아웃이 끝난 뒤 hidden 처리
      window.setTimeout(() => {
        if (!isOpen) panel.hidden = true;
      }, 250);
    }

    burger.addEventListener("click", () => (isOpen ? close() : open()));

    // 메뉴 항목을 누르면 바로 닫기 (같은 페이지 앵커 이동 대비)
    panel.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", close);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isOpen) close();
    });

    // 가로 회전 등으로 데스크톱 폭이 되면 잠금 해제
    window.addEventListener("resize", () => {
      if (isOpen && window.innerWidth > 768) close();
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
    setupMobileMenu();
    mirrorMenuUnderIntro();
  }

  /**
   * 폰에서 인트로 아래에 메뉴 목록을 둔다 (2026-09-22 지시).
   *
   * 재권님 말씀 — 「메인은 이화면만 있으면될거같아」 ·
   * 「kjc스튜디오는 그전에 그린 높이 거기에다가 그대로 두고 그밑으로 글자들 넣어」.
   *
   * **목록을 새로 적지 않고 모바일 메뉴에서 복제한다.** 같은 목록이 두 곳에
   * 있으면 메뉴를 고칠 때 한쪽만 바뀐다 — `partials/nav.html` 한 곳만 고치면
   * 양쪽이 따라오게 하려는 것이다.
   *
   * **보이고 안 보이고는 CSS 가 정한다** (`home.css` 의 768px 블록).
   * 여기서 창 폭을 재지 않는 이유는, 재서 넣으면 **폰을 돌리거나 창을 줄일 때**
   * 다시 넣어야 하기 때문이다. 넣어 두고 CSS 가 켜고 끄면 그럴 일이 없다.
   */
  function mirrorMenuUnderIntro() {
    const intro = document.querySelector(".intro");
    const panel = document.querySelector(".nav-mobile");
    if (!intro || !panel) return;
    if (document.querySelector(".intro-links")) return;   /* 두 번 넣지 않는다 */

    const box = document.createElement("nav");
    box.className = "intro-links";
    box.setAttribute("aria-label", "바로가기");
    panel.querySelectorAll("ul").forEach((ul) => box.appendChild(ul.cloneNode(true)));
    intro.insertAdjacentElement("afterend", box);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
