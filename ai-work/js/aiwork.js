/* ==========================================================================
   AI Work — AI 로 컨셉·모델링을 만드는 판

   프로젝트 보드(projects/)의 규칙을 그대로 가져왔다 (2026-09-17 지시).
   다른 것은 칸 이름뿐이다.

     프로젝트 보드   할 일 · 진행중 · 완료
     여기            컨셉 · 캐릭터 모델링 · 애니메이션 · 배경 모델링 · 완료

   작업 하나가 칸을 옮겨 가며 만들어진다. 하위 항목 · 상세창 · 확인 대화상자는
   프로젝트 보드와 같다.

   두 가지가 따로 산다

     data/pipeline.json   바뀌지 않는 틀 — 칸 이름 · 질문 · 후보 도구
     서버 / localStorage  화면에서 만드는 작업

   그래서 pipeline.json 을 고쳐도 만들어 둔 것이 날아가지 않는다. 반대도 같다.
   저장 자리는 API 보드가 쓰는 것과 같다 — /api/board/doc/<이름>.
   ========================================================================== */

const $ = (id) => document.getElementById(id);

const API = "/api/board/doc/ai-work";
const LOCAL_KEY = "kjc-ai-work-v3";
const SYNC_DELAY = 800;

/* 칸은 pipeline.json 이 정한다. 프로젝트 보드의 COLUMNS 자리다 —
   거기서는 할 일·진행중·완료였고 여기서는 컨셉·모델링·… 이다. */
function columns() { return (frame && frame.stages) || []; }

/* 후보 도구 상태 — pipeline.json 의 tools[].status */
const TOOL_STATUS = {
  read:  { label: "조사만",   cls: "is-read" },
  tried: { label: "돌려봄",   cls: "is-tried" },
  use:   { label: "쓰기로 함", cls: "is-use" },
  no:    { label: "안 됨",    cls: "is-no" },
};

let frame = null;      /* pipeline.json */
let tasks = [];        /* [ {id, text, column, subs[], tools[], memo, …} ] */
let openTask = null;   /* 상세창에 띄운 작업 */
let syncTimer = null, syncing = false, pending = false;

try { tasks = JSON.parse(localStorage.getItem(LOCAL_KEY)) || []; } catch (e) { tasks = []; }
if (!Array.isArray(tasks)) tasks = [];

/* ── 잔손질 ─────────────────────────────── */

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* JSON 안에서 쓰는 아주 작은 강조. **굵게** 와 __기울임__ 둘뿐이다. */
function mark(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<em>$1</em>");
}

function uid(p) {
  return (p || "t") + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function stageOf(id) {
  return columns().find((s) => s.id === id) || null;
}

function subStat(t) {
  const list = t.subs || [];
  const done = list.filter((s) => s.done).length;
  return { done: done, total: list.length };
}

function touch(t) { t.updatedAt = Date.now(); }

/* ── 확인 대화상자 ──────────────────────── */
/* 프로젝트 보드의 ask() 와 같은 규칙이다. 추가도 삭제도 이것을 거친다.
   이름을 받아야 하면 input:true. 한글 조합 중 Enter 는 확정이므로 거른다. */
function ask(opts) {
  return new Promise((resolve) => {
    const back = document.createElement("div");
    back.className = "aw-ask-back";
    back.innerHTML = `
      <div class="aw-ask" role="dialog" aria-modal="true">
        <div class="aw-ask-t">${esc(opts.title)}</div>
        ${opts.desc ? `<div class="aw-ask-d">${esc(opts.desc)}</div>` : ""}
        ${opts.input ? `<input class="aw-ask-in" type="text" placeholder="${esc(opts.placeholder || "")}">` : ""}
        <div class="aw-ask-q">${esc(opts.ask || "정말로 진행하시겠습니까?")}</div>
        <div class="aw-ask-btns">
          <button class="aw-ask-no" type="button">취소</button>
          <button class="aw-ask-ok${opts.danger ? " is-danger" : ""}" type="button">${esc(opts.okText || "확인")}</button>
        </div>
      </div>`;
    document.body.appendChild(back);

    const input = back.querySelector(".aw-ask-in");
    const ok = back.querySelector(".aw-ask-ok");
    const no = back.querySelector(".aw-ask-no");

    const close = (v) => { back.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => { if (e.key === "Escape") close(null); };

    ok.addEventListener("click", () => {
      if (!opts.input) return close(true);
      const v = (input.value || "").trim();
      if (!v) { input.focus(); return; }
      close(v);
    });
    no.addEventListener("click", () => close(null));
    back.addEventListener("click", (e) => { if (e.target === back) close(null); });
    document.addEventListener("keydown", onKey);

    if (input) {
      input.focus();
      input.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        /* 한글을 조합하는 중의 Enter 는 「글자 확정」이지 「입력 끝」이 아니다.
           거르지 않으면 첫 글자만 들어간 채 창이 닫힌다. */
        if (e.isComposing || e.keyCode === 229) return;
        e.preventDefault();
        ok.click();
      });
    }
  });
}

/* ── 저장 ───────────────────────────────── */

function setSaved(text, cls) {
  const el = $("aw-saved");
  el.textContent = text;
  el.className = "aw-saved" + (cls ? " " + cls : "");
}

function persistLocal() {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(tasks));
  } catch (e) {}
}

function save() {
  persistLocal();
  setSaved("저장 중…", "is-busy");
  if (syncing) { pending = true; return; }
  clearTimeout(syncTimer);
  syncTimer = setTimeout(sync, SYNC_DELAY);
}

function sync() {
  syncing = true; pending = false;
  fetch(API, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ data: { tasks: tasks } }),
  })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(() => setSaved("서버에 저장됨", "is-ok"))
    .catch(() => setSaved("이 브라우저에만 저장됨", "is-warn"))
    .then(() => {
      syncing = false;
      if (pending) { clearTimeout(syncTimer); syncTimer = setTimeout(sync, SYNC_DELAY); }
    });
}

function loadFromServer() {
  return fetch(API, { headers: { accept: "application/json" } })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((body) => {
      if (body && body.ok && body.data && body.data.tasks) {
        tasks = body.data.tasks;
        persistLocal();
        setSaved("서버에서 불러옴", "is-ok");
        return;
      }
      setSaved("서버 연결됨", "is-ok");
      if (tasks.length) save();
    })
    .catch(() => setSaved("이 브라우저에만 저장됨", "is-warn"));
}

/* ── 작업 카드 ──────────────────────────── */

function drawCard(t) {
  const el = document.createElement("article");
  el.className = "aw-card";
  el.dataset.id = t.id;
  el.draggable = true;

  const st = subStat(t);
  const tools = (t.tools || []).map((x) => `<span class="aw-chip">${esc(x)}</span>`).join("");

  el.innerHTML = `
    <div class="aw-card-t">${esc(t.text)}</div>
    ${tools ? `<div class="aw-card-m">${tools}</div>` : ""}
    ${st.total ? `<div class="aw-card-sub"></div>` : ""}`;

  /* 하위 항목은 카드에서도 바로 체크한다 — 프로젝트 보드와 같다 */
  if (st.total) {
    const box = el.querySelector(".aw-card-sub");
    (t.subs || []).forEach((s) => {
      const row = document.createElement("label");
      row.className = "aw-card-s" + (s.done ? " is-on" : "");
      row.innerHTML = `<span class="aw-card-box"></span><span>${esc(s.text)}</span>`;
      row.addEventListener("click", (e) => {
        e.stopPropagation();
        s.done = !s.done;
        touch(t); save(); render();
      });
      box.appendChild(row);
    });
  }

  el.addEventListener("click", () => openDetail(t));

  el.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", t.id);
    e.dataTransfer.effectAllowed = "move";
    el.classList.add("is-dragging");
  });
  el.addEventListener("dragend", () => el.classList.remove("is-dragging"));

  return el;
}

function drawLanes() {
  const host = $("aw-lanes");
  host.innerHTML = "";

  columns().forEach((col) => {
    const mine = tasks.filter((t) => t.column === col.id);

    const tools = (col.tools || []).map((t) => {
      const st = TOOL_STATUS[t.status] || TOOL_STATUS.read;
      return `<div class="aw-cand">
        <div class="aw-cand-h"><b>${esc(t.name)}</b>
          <span class="aw-cand-st ${st.cls}">${esc(st.label)}</span></div>
        <div class="aw-cand-m">${mark(t.note)}</div></div>`;
    }).join("");

    const lane = document.createElement("section");
    lane.className = "aw-lane";
    lane.innerHTML = `
      <div class="aw-lane-h">
        <span class="aw-lane-no">${esc(col.no)}</span>
        <span class="aw-lane-t tone-${esc(col.tone || "neutral")}">${esc(col.label)}</span>
        <span class="aw-lane-n">${mine.length}</span>
      </div>
      ${col.question ? `<div class="aw-lane-q">
        <span class="aw-lane-q-k">정해야 할 것</span>
        ${esc(col.question)}</div>` : ""}
      ${col.blocker ? `<div class="aw-blocker">
        <b>${esc(col.blocker.title)}</b>
        <span>${mark(col.blocker.body)}</span></div>` : ""}
      <div class="aw-lane-b"></div>
      <button class="aw-lane-add" type="button">＋ 작업 추가</button>
      ${tools ? `<details class="aw-cands">
        <summary>후보 도구 ${col.tools.length}개</summary>
        <div class="aw-cands-b">${tools}</div></details>` : ""}`;

    const body = lane.querySelector(".aw-lane-b");
    if (mine.length === 0) {
      body.innerHTML = `<div class="aw-lane-empty">비어 있습니다</div>`;
    } else {
      mine.forEach((t) => body.appendChild(drawCard(t)));
    }

    /* 칸 사이로 끌어 옮기기 — 작업이 컨셉에서 모델링으로 넘어간다 */
    lane.addEventListener("dragover", (e) => { e.preventDefault(); lane.classList.add("is-over"); });
    lane.addEventListener("dragleave", () => lane.classList.remove("is-over"));
    lane.addEventListener("drop", (e) => {
      e.preventDefault();
      lane.classList.remove("is-over");
      const id = e.dataTransfer.getData("text/plain");
      const t = tasks.find((x) => x.id === id);
      if (!t || t.column === col.id) return;
      t.column = col.id;
      touch(t); save(); render();
    });

    lane.querySelector(".aw-lane-add").addEventListener("click", () => addTask(col));
    host.appendChild(lane);
  });
}

function addTask(col) {
  ask({
    title: "새 작업",
    desc: col.label,
    input: true,
    placeholder: "무엇을 합니까?",
    ask: "정말로 추가하시겠습니까?",
    okText: "추가",
  }).then((text) => {
    if (!text) return;
    tasks.push({
      id: uid("t"),
      text: text,
      column: col.id,
      subs: [],
      tools: [],
      memo: "",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    save();
    render();
  });
}

/* ── 상세창 ─────────────────────────────── */

function openDetail(t) {
  openTask = t;
  drawDetail();
}

function closeDetail() { openTask = null; drawDetail(); }

function drawDetail() {
  const host = $("aw-detail");
  if (!openTask) { host.innerHTML = ""; host.hidden = true; return; }

  const t = openTask;
  /* 칸을 옮기면 후보 도구도 그 칸 것으로 바뀐다 — 컨셉 단계와 모델링 단계는
     쓰는 도구가 다르기 때문이다. */
  const stage = stageOf(t.column) || columns()[0] || { tools: [] };
  const st = subStat(t);


  host.hidden = false;
  host.innerHTML = `
    <div class="aw-modal" role="dialog" aria-modal="true">
      <div class="aw-m-h">
        <span class="aw-m-no">${esc(stage.no)} ${esc(stage.label)}</span>
        <button class="aw-m-x" type="button" title="닫기">✕</button>
      </div>
      <input class="aw-m-title" type="text" value="${esc(t.text)}" placeholder="무엇을 합니까?">

      <div class="aw-m-row">
        <div class="aw-m-k">어느 칸</div>
        <div class="aw-m-seg" id="aw-m-seg"></div>
      </div>

      <div class="aw-m-row">
        <div class="aw-m-k">쓰는 도구</div>
        <div class="aw-m-chips" id="aw-m-tools"></div>
      </div>

      <div class="aw-m-row">
        <div class="aw-m-k">하위 항목 <span class="aw-m-cnt">${st.done} / ${st.total}</span></div>
        <div class="aw-m-subs" id="aw-m-subs"></div>
        <button class="aw-m-addsub" type="button">＋ 하위 항목 추가</button>
      </div>

      <div class="aw-m-row">
        <div class="aw-m-k">메모</div>
        <textarea class="aw-m-memo" placeholder="해보고 알게 된 것을 적어 둡니다">${esc(t.memo || "")}</textarea>
      </div>

      <div class="aw-m-foot">
        <button class="aw-m-del" type="button">삭제</button>
        <button class="aw-m-done" type="button">닫기</button>
      </div>
    </div>`;

  /* 칸 옮기기 */
  const seg = host.querySelector("#aw-m-seg");
  columns().forEach((c) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "aw-seg-b" + (c.id === t.column ? " is-on" : "");
    b.textContent = c.label;
    b.addEventListener("click", () => { t.column = c.id; touch(t); save(); render(); });
    seg.appendChild(b);
  });

  /* 도구 — 그 갈래의 후보에서 고르거나 직접 적는다 */
  const tools = host.querySelector("#aw-m-tools");
  (stage.tools || []).forEach((cand) => {
    const on = (t.tools || []).includes(cand.name);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "aw-chip-b" + (on ? " is-on" : "");
    b.textContent = cand.name;
    b.addEventListener("click", () => {
      t.tools = on ? (t.tools || []).filter((x) => x !== cand.name)
                   : (t.tools || []).concat([cand.name]);
      touch(t); save(); render();
    });
    tools.appendChild(b);
  });
  /* 목록에 없는 도구도 쓸 수 있어야 한다 */
  (t.tools || []).filter((n) => !(stage.tools || []).some((c) => c.name === n)).forEach((n) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "aw-chip-b is-on";
    b.textContent = n;
    b.addEventListener("click", () => {
      t.tools = (t.tools || []).filter((x) => x !== n);
      touch(t); save(); render();
    });
    tools.appendChild(b);
  });
  const addTool = document.createElement("button");
  addTool.type = "button";
  addTool.className = "aw-chip-b is-add";
  addTool.textContent = "＋ 직접 적기";
  addTool.addEventListener("click", () => {
    ask({ title: "도구 추가", input: true, placeholder: "도구 이름",
          ask: "이 작업에 붙일까요?", okText: "추가" }).then((v) => {
      if (!v) return;
      t.tools = (t.tools || []).concat([v]);
      touch(t); save(); render();
    });
  });
  tools.appendChild(addTool);

  /* 하위 항목 */
  const subs = host.querySelector("#aw-m-subs");
  (t.subs || []).forEach((s, i) => {
    const row = document.createElement("div");
    row.className = "aw-m-sub" + (s.done ? " is-on" : "");
    row.innerHTML = `<span class="aw-m-box"></span><span class="aw-m-st">${esc(s.text)}</span>
                     <button class="aw-m-subx" type="button">✕</button>`;
    row.querySelector(".aw-m-box").addEventListener("click", () => {
      s.done = !s.done; touch(t); save(); render();
    });
    row.querySelector(".aw-m-subx").addEventListener("click", () => {
      t.subs.splice(i, 1); touch(t); save(); render();
    });
    subs.appendChild(row);
  });
  if (!(t.subs || []).length) {
    subs.innerHTML = `<div class="aw-m-empty">아직 없습니다</div>`;
  }

  host.querySelector(".aw-m-addsub").addEventListener("click", () => {
    ask({ title: "하위 항목 추가", desc: t.text, input: true,
          placeholder: "무엇을 합니까?", ask: "정말로 추가하시겠습니까?", okText: "추가" })
      .then((v) => {
        if (!v) return;
        if (!Array.isArray(t.subs)) t.subs = [];
        t.subs.push({ id: uid("s"), text: v, done: false });
        touch(t); save(); render();
      });
  });

  /* 제목 · 메모 — 고치면 바로 저장 */
  const title = host.querySelector(".aw-m-title");
  title.addEventListener("change", () => {
    const v = title.value.trim();
    if (v) { t.text = v; touch(t); save(); render(); }
  });
  title.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    if (e.isComposing || e.keyCode === 229) return;   /* 한글 조합 확정 */
    e.preventDefault();
    title.blur();
  });

  const memo = host.querySelector(".aw-m-memo");
  memo.addEventListener("change", () => { t.memo = memo.value; touch(t); save(); });

  /* 삭제 — 추가와 같은 확인을 거친다 */
  host.querySelector(".aw-m-del").addEventListener("click", () => {
    ask({ title: "작업 삭제", desc: t.text, danger: true,
          ask: "정말로 삭제하시겠습니까? 되돌릴 수 없습니다.", okText: "삭제" })
      .then((ok) => {
        if (!ok) return;
        const i = tasks.findIndex((x) => x.id === t.id);
        if (i >= 0) tasks.splice(i, 1);
        openTask = null;
        save(); render();
      });
  });

  host.querySelector(".aw-m-x").addEventListener("click", closeDetail);
  host.querySelector(".aw-m-done").addEventListener("click", closeDetail);
  host.addEventListener("click", (e) => { if (e.target === host) closeDetail(); });
}

/* ── 그리기 ─────────────────────────────── */

function render() {
  drawLanes();
  drawDetail();
}

/* ── 시작 ───────────────────────────────── */

async function init() {
  try {
    const r = await fetch("./data/pipeline.json", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    frame = await r.json();
  } catch (e) {
    $("aw-lanes").innerHTML = `
      <div class="aw-fail">
        <b>틀을 불러오지 못했습니다</b>
        ai-work/data/pipeline.json 을 읽지 못했습니다. 파일이 있는지,
        로컬 서버로 열었는지 확인해 주세요 (file:// 로 열면 막힙니다).
      </div>`;
    setSaved("불러오지 못함", "is-warn");
    console.error("[AI Work] pipeline.json", e);
    return;
  }

  render();               /* 브라우저에 있던 것으로 먼저 */
  await loadFromServer();
  render();               /* 서버 것으로 다시 */
}

init();
