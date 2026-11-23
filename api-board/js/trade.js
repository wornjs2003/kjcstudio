/* ==========================================================================
   API 보드 · 자동 매매 — 룰 칸 · 흐름 · 매매일지 (2026-11-23 · 개발2)
   재권님 「미수 매도 이거의 룰은 계속 개선할 수 있으니 api에 룰 개선 가능하도록 () 만들어놔. 거기에 먼저 정리되어야해」 →
   「먼저 api 거기에 작성해서 올려봐 자세히 보게」 → 이 일에 한해 개발2 가 만듦(「가」 15:1x).

   칸 · 단위 · 범위 · 설명은 서버 한 곳(holdings/server/trade_signal.py RULES)이 /api/kis/trade-journal meta.rules 로 준다 — 여기 박지 않는다.
   값은 룰 문서 trade-set(/api/board/doc/trade-set) — updatedAt 을 실어 써서 두 창이 서로 덮지 않는다(409 면 다시 읽음).
   ========================================================================== */
(function () {
  const J = "/api/kis/trade-journal?days=30";
  const DOC = "/api/board/doc/trade-set";
  const $ = (id) => document.getElementById(id);
  let meta = null, doc = {}, docAt = null, dirty = false;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }
  function won(v) { return v == null ? "—" : Math.round(v).toLocaleString("ko-KR"); }
  function ts(v) {                               // YYYYMMDDHHMMSS → MM-DD HH:MM
    v = String(v || "");
    return v.length >= 12 ? v.slice(4, 6) + "-" + v.slice(6, 8) + " " + v.slice(8, 10) + ":" + v.slice(10, 12) : "—";
  }
  function val(k) { const v = doc[k]; return v === undefined || v === null || v === "" ? null : v; }
  function valid(r, v) {
    if (v === null || v === "" || isNaN(Number(v))) return false;
    const n = Number(v);
    if (r.kind === "int" && !Number.isInteger(n)) return false;
    return n >= r.min && n <= r.max;
  }
  function box(k) {                              // 설명 글의 ( ) — 채운 칸은 그 값 · 빈 칸은 빨간 ( )
    const r = (meta && meta.rules || []).find((x) => x.key === k);
    const v = val(k);
    if (v === null || !r || !valid(r, v)) return '<span class="v empty">( )</span>';
    const t = r.unit === "원" ? Number(v).toLocaleString("ko-KR") : v;
    return '<span class="v">(' + esc(t) + ")</span>" + esc(r.unit === "원" ? "원" : r.unit);
  }

  function drawState() {
    const st = meta || {}, s = st.settings || {};
    const chips = [];
    chips.push(st.send ? '<span class="tr-chip ok">슬랙 보내기 켜짐</span>' : '<span class="tr-chip warn">슬랙 보내기 꺼짐 — 켜기는 재권님 지시</span>');
    chips.push((s.missing || []).length ? '<span class="tr-chip warn">빈 룰 칸 ' + s.missing.length + "</span>" : '<span class="tr-chip ok">룰 칸 다 참</span>');
    chips.push('<span class="tr-chip">룰 판 ' + esc(s.ver || "없음") + "</span>");
    const pcs = st.pcs || [];
    chips.push('<span class="tr-chip' + (pcs.length ? "" : " warn") + '">주문 컴퓨터 ' + (pcs.length ? esc(pcs.join(" · ")) : "없음(서버를 아직 안 읽었거나 열쇠 없음)") + "</span>");
    (st.pcsDropped || []).forEach((d) => chips.push('<span class="tr-chip warn">빠진 컴퓨터 ' + esc(d.name) + " — " + esc(d.why) + "</span>"));
    if (st.error) chips.push('<span class="tr-chip warn">서버 오류 ' + esc(st.error) + "</span>");
    $("trState").innerHTML = chips.join("");
  }

  function drawRules() {
    const rs = (meta && meta.rules) || [];
    $("trRules").innerHTML = rs.map((r) => {
      const v = val(r.key);
      return '<div class="tr-rule"><div class="tr-rule-name">' + esc(r.name) + '</div>' +
        '<div class="tr-rule-in"><input inputmode="decimal" data-k="' + esc(r.key) + '" value="' + esc(v === null ? "" : v) + '" aria-label="' + esc(r.name) + '">' +
        '<span class="tr-rule-unit">' + esc(r.unit) + " · " + esc(Number(r.min).toLocaleString("ko-KR")) + "~" + esc(Number(r.max).toLocaleString("ko-KR")) + "</span></div>" +
        '<div class="tr-rule-desc">' + esc(r.desc) + "</div></div>";
    }).join("");
    $("trRules").querySelectorAll("input").forEach((el) => el.addEventListener("input", onInput));
    check();
  }

  function onInput(e) {
    const k = e.target.dataset.k, t = e.target.value.trim();
    doc[k] = t === "" ? null : Number(t);
    dirty = true;
    check();
    drawFlow();
  }

  function check() {
    let ok = true;
    $("trRules").querySelectorAll("input").forEach((el) => {
      const r = meta.rules.find((x) => x.key === el.dataset.k);
      const t = el.value.trim();
      const bad = t !== "" && !valid(r, t);
      el.classList.toggle("bad", bad);
      if (bad) ok = false;
    });
    $("trSave").disabled = !dirty || !ok;
    $("trMsg").textContent = !ok ? "범위 밖 칸이 있어 저장할 수 없습니다" : dirty ? "저장 전 — 저장하면 룰 판이 바뀌고 주문 컴퓨터에 새 룰이 갑니다(보내기 켜진 때)" : "";
  }

  function tm(k) {                               // 그날 시각 — 서버 meta.times(첫 굳힘 · 스스로 정리 · 다음 거래일) · 못 받으면 「서버 값 못 받음」
    const v = ((meta || {}).times || {})[k];
    return v ? '<span class="v">' + esc(v) + "</span>" : "(서버 값 못 받음)";
  }

  function drawFlow() {
    const st = meta || {};
    $("trFlow").innerHTML =
      "<h3>보내기 (서버)</h3><ol>" +
      "<li>평일 단타 판 첫 굳힘(" + tm("firstLock") + ") 줄 중 굳힘 차례 위 <span class=\"v\">" + esc(st.pickN) + "</span>종목을 슬랙에 한 번 — 종목 코드 · 이름 · 매수금액(단타 판 셈 칸의 첫 굳힘 금액 ÷ 보내는 종목 수) · 굳힘 가격 · 룰 판</li>" +
      "<li>판 매도 룰(손절 · 꺾임 · 고점 · 미달 · 횡보 · 매도 시각 — 단타 판 셈 칸 그대로)에 걸리면 그 종목 「팔아라」 한 번</li>" +
      "<li>룰 칸이 바뀔 때마다 · 매일 <span class=\"v\">" + esc(st.rulesAt) + "</span> 에 서명한 룰 줄 한 번</li></ol>" +
      "<h3>매수 (주문 컴퓨터)</h3><ol>" +
      "<li>서명 · 늦은 메시지(슬랙 서버 시각 기준) · 같은 번호 한 번을 본 뒤, 「이 번호 주문함」 을 먼저 디스크에 적는다</li>" +
      "<li>수량 = 받은 매수금액 ÷ 현재가(소수 버림) · 0주면 「못 삼」 · 돈이 실제로 막히는 자리는 주문 컴퓨터 설정의 한 번 · 하루 금액 한도(이 칸은 서버가 보내는 값)</li>" +
      "<li>현재가가 굳힘 가격보다 " + box("buyMaxUpPct") + " 넘게 높으면 안 삼(「못 삼: 오름」)</li>" +
      "<li>시장가로 넣고, 다 안 사졌으면 남은 수량을 " + box("buyRetrySec") + " 마다 다시 시장가 · VI 단일가 중엔 기다림</li>" +
      "<li>그만두는 때 — 현재가가 굳힘 가격보다 " + box("buyMaxUpPct") + " 넘게 오름 · 첫 주문 뒤 " + box("buyMaxMin") + " 지남 → 산 만큼만 들고 감</li></ol>" +
      "<h3>매도 (주문 컴퓨터)</h3><ol>" +
      "<li>「팔아라」 를 받으면 그 번호로 실제 체결된 수량만 시장가로(잔고 전체가 아님) · 늦게 온 「팔아라」 도 판다</li>" +
      "<li>안 팔린 수량은 " + box("sellRetrySec") + " 마다 다시 시장가</li>" +
      "<li>" + tm("cleanAt") + " 뒤에도 남으면 장 끝 동시호가에 넣고, 그래도 남으면 「못 팖 · 남은 수량」 을 보내고 다음 거래일 " + tm("reopenAt") + " 다시</li>" +
      "<li>서버가 꺼져 「팔아라」 가 안 와도 " + tm("cleanAt") + " 전에 남은 것을 스스로 시장가로 판다</li></ol>" +
      "<h3>결과 · 기록</h3><ul>" +
      "<li>매도가 끝나면(또는 못 사면) 결과 줄 — 매수가 · 매도가 · 수량 · 시세차익 · 세금 · 까닭 — 을 서명해 보내고 아래 매매일지에 쌓인다</li>" +
      "<li>주문 컴퓨터는 단계마다 로그를 남긴다(받음 · 디스크 기록 · 증권사 요청 · 응답 · 체결 · 결정 까닭) · 창에서 골라 보고 파일로 내보내 여기서 되짚는다 · 열쇠 · 계좌번호는 가림</li>" +
      "<li>모든 메시지는 컴퓨터마다 다른 열쇠로 서명 — 열쇠 없는 글은 주문 · 일지를 못 움직인다</li></ul>";
  }

  function drawLog(rows) {
    if (!rows.length) {
      $("trLog").innerHTML = '<div class="tr-empty">아직 보낸 신호가 없습니다' + (meta && !meta.send ? " — 슬랙 보내기가 꺼져 있어 일지에 줄을 안 만듭니다" : "") + "</div>";
      return;
    }
    const head = "<tr><th>날짜</th><th>차례</th><th>종목</th><th>매수금액</th><th>굳힘 가격</th><th>상태</th><th>팔아라</th><th>컴퓨터</th><th>매수가</th><th>매도가</th><th>수량</th><th>차익</th><th>세금</th><th>까닭</th></tr>";
    const body = rows.map((r) => {
      const res = r.results && r.results.length ? r.results : [null];
      return res.map((x, i) => "<tr>" +
        (i ? '<td colspan="7"></td>' :
          "<td>" + esc(String(r.day).slice(4, 6) + "-" + String(r.day).slice(6, 8)) + "</td><td>" + esc(r.rank) + '</td><td class="l">' + esc(r.name) + " " + esc(r.code) + "</td>" +
          "<td>" + won(r.amount_won) + "</td><td>" + won(r.lock_px) + '</td><td class="l">' + esc(r.status) + (r.note ? " · " + esc(r.note) : "") + "</td>" +
          "<td>" + (r.sell_sent_at ? esc(r.sell_why) + " " + ts(r.sell_sent_at) : "—") + "</td>") +
        (x ? "<td>" + esc(x.pc) + "</td><td>" + won(x.buy_px) + "</td><td>" + won(x.sell_px) + "</td><td>" + esc(x.qty) + "</td><td>" + won(x.profit_won) +
          "</td><td>" + won(x.tax_won) + '</td><td class="l">' + esc(x.why || "") + "</td>" : '<td colspan="7" class="l">결과 아직 없음</td>') + "</tr>").join("");
    }).join("");
    $("trLog").innerHTML = "<table><thead>" + head + "</thead><tbody>" + body + "</tbody></table>";
  }

  function load() {
    $("trMsg").textContent = "불러오는 중…";
    Promise.all([
      fetch(J, { headers: { accept: "application/json" } }).then((r) => r.json()),
      fetch(DOC, { headers: { accept: "application/json" } }).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ]).then(([j, d]) => {
      meta = j.meta || {};
      doc = Object.assign({}, (d && d.data) || {});
      docAt = (d && d.updatedAt) || null;
      dirty = false;
      drawState(); drawRules(); drawFlow(); drawLog(j.data || []);
      $("trMsg").textContent = "";
    }).catch(() => {
      $("trState").innerHTML = '<span class="tr-chip warn">서버 값을 못 받음 — 룰 칸을 그릴 수 없습니다</span>';
      $("trMsg").textContent = "";
    });
  }

  function save() {
    const data = {};
    meta.rules.forEach((r) => { data[r.key] = val(r.key) === null ? null : Number(val(r.key)); });
    $("trSave").disabled = true;
    $("trMsg").textContent = "저장 중…";
    fetch(DOC, {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify(docAt ? { data: data, updatedAt: docAt } : { data: data }),
    }).then((r) => {
      if (r.status === 409) { $("trMsg").textContent = "그 사이 다른 곳에서 룰을 바꿨습니다 — 다시 읽었으니 확인 뒤 다시 저장해 주십시오"; load(); return; }
      if (!r.ok) throw new Error(r.status);
      load();
      $("trMsg").textContent = "저장했습니다";
    }).catch(() => { $("trMsg").textContent = "저장 못 함 — 서버를 확인해 주십시오"; check(); });
  }

  $("trSave").addEventListener("click", save);
  $("trReload").addEventListener("click", load);
  load();
})();
