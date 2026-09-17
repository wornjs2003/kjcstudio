/* ==========================================================================
   AI Work — 작업 프로세스를 정하는 판

   data/pipeline.json 을 읽어 화면을 그린다. 내용을 바꿀 때 이 파일을 고치지
   않는다 — JSON 만 고치면 된다.

   위 통계(조사한 도구 · 돌려본 것 · 정한 것 · 모르는 것)는 **세어서** 낸다.
   숫자를 따로 적어 두면 내용과 어긋나고, 어긋나도 화면은 멀쩡해 보인다.
   CLAUDE.md 「같은 값은 한 곳에만 둔다」 와 같은 이유다.
   ========================================================================== */

const $ = (id) => document.getElementById(id);

/* 상태 넷. JSON 의 status 값과 화면에 적을 말을 여기 한 곳에 둔다. */
const STATUS = {
  read:  { label: "조사만",   cls: "is-read" },
  tried: { label: "돌려봄",   cls: "is-tried" },
  use:   { label: "쓰기로 함", cls: "is-use" },
  no:    { label: "안 됨",    cls: "is-no" },
};

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* JSON 안에서 쓰는 아주 작은 강조 표시.
   **굵게** 와 __기울임__ 둘뿐이다. 이 이상은 JSON 에 HTML 을 적게 되어
   내용과 화면이 뒤섞인다. */
function mark(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<em>$1</em>");
}

function drawStats(stages, unknownList) {
  const all = stages.flatMap((s) => s.tools || []);
  const n = (k) => all.filter((t) => t.status === k).length;

  /* 「아직 모르는 것」은 두 곳에 있다 — 단계마다 붙은 것과 아래 목록.
     둘을 합쳐 센다. 한쪽만 세면 화면과 숫자가 어긋난다. */
  const unknownCount = stages.filter((s) => s.unknown).length + (unknownList || []).length;

  const rows = [
    { k: "조사한 도구",   v: all.length,  n: "읽어만 봤습니다" },
    { k: "직접 돌려본 것", v: n("tried"), n: "여기부터 시작합니다" },
    { k: "쓰기로 정한 것", v: n("use"),   n: "돌려본 뒤에 정합니다" },
    { k: "아직 모르는 것", v: unknownCount, n: "빨간 칸" },
  ];

  $("aw-stats").innerHTML = rows.map((r) => `
    <div class="aw-stat">
      <div class="k">${esc(r.k)}</div>
      <div class="v">${r.v}<small>개</small></div>
      <div class="n">${esc(r.n)}</div>
    </div>`).join("");

  /* 머리말 한 줄 — 지금 어디까지 왔는지 */
  const stamp = $("aw-stamp");
  const tried = n("tried");
  if (tried === 0) {
    stamp.textContent = "아직 직접 돌려본 것 0개";
    stamp.classList.remove("is-going");
  } else {
    stamp.textContent = `직접 돌려본 것 ${tried}개`;
    stamp.classList.add("is-going");
  }
}

function drawPanes(stages) {
  $("aw-panes").innerHTML = stages.map((s) => {
    const tools = (s.tools || []).map((t) => {
      const st = STATUS[t.status] || STATUS.read;
      return `<div class="aw-tool">
        <div class="aw-tool-h">
          <b>${esc(t.name)}</b>
          <span class="aw-st ${st.cls}">${esc(st.label)}</span>
        </div>
        <div class="aw-tool-m">${mark(t.note)}</div>
      </div>`;
    }).join("");

    const unknown = s.unknown ? `
      <div class="aw-unknown">
        <b>${esc(s.unknown.title)}</b>
        <span>${mark(s.unknown.body)}</span>
      </div>` : "";

    return `<section class="aw-pane">
      <div class="aw-pane-h"><span class="no">${esc(s.no)}</span><b>${esc(s.label)}</b></div>
      <p class="aw-pane-d">${esc(s.desc)}</p>
      <div class="aw-q">
        <div class="aw-q-k">정해야 할 것</div>
        <div class="aw-q-v">${esc(s.question)}</div>
      </div>
      ${tools}
      ${unknown}
    </section>`;
  }).join("");
}

function drawLists(known, unknown) {
  const li = (arr) => (arr || []).map((x) => `<li>${mark(x)}</li>`).join("");
  $("aw-known").innerHTML = li(known);
  $("aw-unknown").innerHTML = li(unknown);
}

async function init() {
  let doc;
  try {
    const r = await fetch("./data/pipeline.json", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    doc = await r.json();
  } catch (e) {
    $("aw-panes").innerHTML = `
      <div class="aw-fail">
        <b>내용을 불러오지 못했습니다</b>
        ai-work/data/pipeline.json 을 읽지 못했습니다. 파일이 있는지,
        로컬 서버로 열었는지 확인해 주세요 (file:// 로 열면 막힙니다).
      </div>`;
    $("aw-stamp").textContent = "불러오지 못함";
    console.error("[AI Work] pipeline.json", e);
    return;
  }

  const stages = doc.stages || [];
  drawStats(stages, doc["모르는것"]);
  drawPanes(stages);
  drawLists(doc["확인된것"], doc["모르는것"]);
}

init();
