/* ==========================================================================
   보드 저장 층 — 세 보드가 함께 쓴다 (2026-10-03 · 보드 8번)

   재권님 「응 그래」 — 자리는 이 파일(보드 레인), 옮기는 것은 **프로젝트 보드부터**.
   AI 작업 판(`ai-work/` · 엔진_개발)과 API 보드(`api-board/` · 주인 정해진 뒤)는
   각 주인이 이것을 걸면서 옮긴다. 걸면 이 파일은 **「거는 쪽이 둘 이상인 파일」**
   이 되고, 고칠 때 훅이 그 화면들을 알려 준다.

   ── 하는 일 ──
     1. 바뀌면 브라우저에 바로 남긴다(부르는 쪽의 `persistLocal`)
     2. 서버에는 `delay` 만큼 모아서 한 번 보낸다 — 타이핑마다 부르지 않으려고
     3. **`updatedAt` 을 실어 보낸다.** 그 사이 남이 썼으면 서버가 **409** 로 거절한다
     4. 409 면 다시 읽어 **셋(그때 · 내 것 · 서버 것)** 을 부르는 쪽의 `merge` 에 넘긴다.
        자동으로 합쳐지면 다시 보내고, 같은 자리를 둘 다 고쳤으면 `decide` 로 묻는다
     5. 서버가 없거나 실패해도 화면은 그대로 돈다 — 「이 브라우저에만 저장됨」

   ── 부르는 쪽이 주는 것 ──
     name          문서 이름 → `/api/board/doc/<name>`
     delay         모아 보내기(ms) · 없으면 1000
     snapshot()    지금 화면 → 문서(깊은 복사)
     apply(doc)    문서 → 화면(그리기까지). 서버에서 읽었을 때 · 합친 뒤에 부른다
     hasData(doc)  서버 문서가 **찬 것인가** — 비었으면 브라우저 것을 올린다
     empty         서버가 비었을 때의 「그때」(base) — 올리는 것이 전부 내 변경이다
     hasLocal()    브라우저에 올릴 것이 있나
     persistLocal()  브라우저에 남긴다(키는 부르는 쪽이 정한다)
     merge(base, mine, theirs) → { doc, conflicts }   없으면 늘 충돌로 본다
     decide(conflicts) → Promise(true = 서버 것으로 · false = 내 것으로)
     status(text, cls) 저장 상태 글

   ── 돌려주는 것 ──
     load()        서버에서 읽는다(처음 한 번)
     save(flash)   바뀌었다 — 남기고 모아 보낸다. `flash === false` 면 「저장 중…」 을 안 띄운다
     alive         null 아직 모름 · true 서버 저장됨 · false 브라우저만

   **합치는 방법은 여기 두지 않는다.** 문서 모양이 보드마다 달라서다
   (프로젝트 보드는 카드 단위로 합치고 접힘은 내 것을 쓴다 — `projects/index.html`).
   ========================================================================== */

function createBoardStore(o) {
  const API = "/api/board/doc/" + o.name;
  const DELAY = o.delay || 1000;

  /* ── 덮어쓰기를 막기 위한 두 값 (2026-09-30 · 프로젝트 보드에서 옮겨 옴) ──
       baseAt   마지막으로 서버와 맞춘 시각 — PUT 에 실어 보낸다
       baseDoc  **그때의 내용.** 합칠 때 「무엇을 내가 바꿨나」 를 알려면 셋이 필요하다
     **메모리에만 둔다.** 새로고침하면 `load()` 가 다시 채운다. `localStorage` 에
     두면 탭이 여럿일 때 서로 덮어쓴다.
     ⚠️ **`baseDoc` 이 없으면 합칠 수 없으므로 충돌로 본다** — 조용히 덮는 것보다 낫다. */
  let baseAt = null;
  let baseDoc = null;
  let syncTimer = null;
  let syncing = false;
  let pending = false;      /* 저장 중에 또 바뀌었는지 */
  let alive = null;

  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /* 한 번 보내고 **상태와 몸통을 함께** 돌려준다. `fetch` 는 409 를 실패로 보지
     않으므로(`res.ok` 가 false 일 뿐 예외가 아님) 상태를 직접 읽어 가른다. */
  function putDoc(doc, at) {
    const body = at ? { data: doc, updatedAt: at } : { data: doc };
    return fetch(API, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().catch(function () { return {}; })
        .then(function (b) { return { status: res.status, body: b }; });
    });
  }

  /* 합친 결과·서버 것을 화면에 올린다 */
  function applyDoc(doc) {
    o.apply(doc);
    o.persistLocal();
  }

  function markSynced(doc, at) {
    baseDoc = clone(doc);
    baseAt = at || null;
    alive = true;
    o.status("서버에 저장됨", "ok");
  }

  function scheduleSync() {
    if (syncing) { pending = true; return; }
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncToServer, DELAY);
  }

  function save(flash) {
    o.persistLocal();
    scheduleSync();
    if (flash !== false && alive !== false) o.status("저장 중…", "busy");
  }

  /* 사람에게 묻고 고른 대로 한다. **어느 쪽을 골라도 무엇이 사라지는지 화면에
     적혀 있다**(부르는 쪽의 `decide`). */
  function decide(conflicts, mine, theirs, at) {
    return o.decide(conflicts).then(function (ok) {
      if (ok) {                      /* 서버 것으로 */
        applyDoc(theirs);
        markSynced(theirs, at);
        o.status("서버에서 불러옴", "ok");
        return;
      }
      /* 내 것으로 — 서버의 지금 `updatedAt` 을 실어 보낸다 */
      return putDoc(mine, at).then(function (r) {
        if (r.status >= 400) { pending = true; o.status("다시 저장합니다…", "busy"); return; }
        markSynced(mine, r.body && r.body.updatedAt);
      });
    });
  }

  function syncToServer() {
    syncing = true;
    pending = false;
    /* **보내는 순간의 내용을 붙들어 둔다.** 합칠 때 「내 것」 이 무엇이었는지
       알아야 하는데, 그 사이에 화면이 또 바뀔 수 있다. */
    const mine = o.snapshot();
    putDoc(mine, baseAt)
      .then(function (r) {
        if (r.status !== 409) {
          if (r.status >= 400) throw new Error("HTTP " + r.status);
          markSynced(mine, r.body && r.body.updatedAt);
          return;
        }
        /* 409 — 그 사이에 남이 썼다. **409 는 `updatedAt` 만 주고 내용은 안 준다.**
           다시 읽어야 한다. */
        o.status("합치는 중…", "busy");
        return fetch(API, { headers: { accept: "application/json" } })
          .then(function (res) { return res.json(); })
          .then(function (body) {
            const theirs = (body && body.data) || clone(o.empty);
            const at = body && body.updatedAt;
            /* **`baseDoc` 이 없으면 합칠 수 없다** — 셋 중 하나가 비면 「무엇을 내가
               바꿨나」 를 알 길이 없다. 조용히 덮지 않는다. 합치는 함수가 없어도 같다. */
            if (!baseDoc) return decide(["이전 상태를 모릅니다"], mine, theirs, at);
            if (!o.merge) return decide(["다른 곳에서 함께 바뀌었습니다"], mine, theirs, at);
            const m = o.merge(baseDoc, mine, theirs);
            if (m.conflicts.length) return decide(m.conflicts, mine, theirs, at);
            /* 자동으로 합쳐졌다 — 합친 것을 다시 보낸다. **여기서 또 409 가 나면 더
               시도하지 않는다**(그 사이 세 번째 변경이 들어온 것). 다음 저장 때 다시 합쳐진다. */
            applyDoc(m.doc);
            return putDoc(m.doc, at).then(function (r2) {
              if (r2.status === 409) { o.status("다시 저장합니다…", "busy"); pending = true; return; }
              if (r2.status >= 400) throw new Error("HTTP " + r2.status);
              markSynced(m.doc, r2.body && r2.body.updatedAt);
            });
          });
      })
      .catch(function () {
        alive = false;
        o.status("이 브라우저에만 저장됨", "warn");
      })
      .then(function () {
        syncing = false;
        if (pending) scheduleSync();
      });
  }

  /* 서버에서 불러오기 — 실패하면 브라우저에 있던 내용으로 간다 */
  function load() {
    return fetch(API, { headers: { accept: "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (body) {
        alive = true;
        /* **읽은 시각과 내용을 들고 있는다.** 이것이 없으면 나중에 충돌이 났을 때
           「무엇을 내가 바꿨나」 를 알 수 없다. */
        baseAt = (body && body.updatedAt) || null;

        if (body && body.ok && body.data && o.hasData(body.data)) {
          o.apply(body.data);
          /* 화면이 고쳐 담은 뒤의 모양을 「그때」 로 — 부르는 쪽이 빠진 값을 채울 수 있다 */
          baseDoc = clone(o.snapshot());
          o.persistLocal();
          o.status("서버에서 불러옴", "ok");
          return;
        }

        /* 서버에 아직 아무것도 없으면, 이 브라우저에 있던 내용을 올려 둔다.
           **그때의 base 는 「빈 것」** 이다 — 올리는 것이 전부 내 변경이다. */
        baseDoc = clone(o.empty);
        o.status("서버 연결됨", "ok");
        if (o.hasLocal()) scheduleSync();
      })
      .catch(function () {
        alive = false;
        /* **못 읽었으면 base 가 없다.** 남겨 두면 낡은 것으로 합치게 된다. */
        baseAt = null;
        baseDoc = null;
        o.status("이 브라우저에만 저장됨", "warn");
      });
  }

  return {
    load: load,
    save: save,
    get alive() { return alive; }
  };
}
