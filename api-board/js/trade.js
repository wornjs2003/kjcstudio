/* ==========================================================================
   API 보드 · 자동 매매 — 다섯 갈래(한눈에 · 흐름 · 룰 · 안전장치 · 준비할 것) + 매매일지
   처음 판 2026-11-23 · 개발2 — 재권님 「미수 매도 이거의 룰은 계속 개선할 수 있으니 api에 룰 개선 가능하도록 () 만들어놔」 →
   「먼저 api 거기에 작성해서 올려봐 자세히 보게」.
   다섯 갈래로 다시 짬 2026-11-24 · 개발3 — 재권님 「카테고리별로 해서 이해하기 쉽게 보기도 쉽게 해줘」 → 「안부터 만들어」.

   칸 · 단위 · 범위 · 설명은 서버 한 곳(holdings/server/trade_signal.py RULES)이 /api/kis/trade-journal meta.rules 로 준다 — 여기 박지 않는다.
   시각 · 차례 수 · 보내기 스위치 · 주문 컴퓨터 이름도 같은 meta 에서 받는다(「설명 글에는 정해진 값을 적는다」).
   값은 룰 문서 trade-set(/api/board/doc/trade-set) — updatedAt 을 실어 써서 두 창이 서로 덮지 않는다(409 면 다시 읽음).

   「준비할 것」 의 주문 컴퓨터 쪽 줄(모의 앱키 · 계좌번호 · 실전 잠금 · 실행 파일)은 서버가 모른다 — 그 컴퓨터 설정(holdings/trader config.json)에만 있다.
   그래서 손으로 적은 목록(PREP_AT 에 적은 날)이고, 서버가 아는 줄(룰 칸 · 보내기 · 컴퓨터 열쇠)만 지금 값으로 바뀐다.
   ========================================================================== */
(function () {
  const J = "/api/kis/trade-journal?days=30";
  const DOC = "/api/board/doc/trade-set";
  const PREP_AT = "2026-11-24";                  // 손으로 적은 줄을 적은 날 — 주문 컴퓨터 쪽 사정이 바뀌면 이 날과 함께 고친다
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
  function rules() { return (meta && meta.rules) || []; }
  function val(k) { const v = doc[k]; return v === undefined || v === null || v === "" ? null : v; }
  function valid(r, v) {
    if (v === null || v === "" || isNaN(Number(v))) return false;
    const n = Number(v);
    if (r.kind === "int" && !Number.isInteger(n)) return false;
    return n >= r.min && n <= r.max;
  }
  function box(k) {                              // 설명 글의 ( ) — 채운 칸은 그 값 · 빈 칸은 빨간 ( )
    const r = rules().find((x) => x.key === k);
    const v = val(k);
    if (v === null || !r || !valid(r, v)) return '<span class="v empty">( )</span>';
    const t = r.unit === "원" ? Number(v).toLocaleString("ko-KR") : v;
    return '<span class="v">(' + esc(t) + ")</span>" + esc(r.unit);
  }
  function tm(k) {                               // 그날 시각 — 서버 meta.times · 못 받으면 「서버 값 못 받음」
    const v = ((meta || {}).times || {})[k];
    return v ? '<span class="v">' + esc(v) + "</span>" : "(서버 값 못 받음)";
  }
  function sv(v) { return v === undefined || v === null || v === "" ? "(서버 값 못 받음)" : '<span class="v">' + esc(v) + "</span>"; }
  function missing() {                           // 빈 룰 칸 — 화면에서 고친 뒤 저장 전이면 화면 값으로 센다
    return rules().filter((r) => !valid(r, val(r.key)));
  }
  function chip(cls, t) { return '<span class="tr-chip ' + cls + '">' + t + "</span>"; }

  /* ── 5 준비할 것 — 한 목록이 「한눈에」 의 재권님 손 칸도 만든다 ── */
  function prepRows() {
    const st = meta || {}, pcs = st.pcs || [], miss = missing();
    const LIVE = "서버 지금 값", HAND = "모름 — 주문 컴퓨터에만 있음 · " + PREP_AT + " 적음";
    return [
      { what: "한국투자 모의투자 신청", who: "재권님", done: null, how: HAND },
      { what: "모의투자 앱키 · 비밀키 받기(컴퓨터마다 따로)", who: "재권님", done: null, how: HAND },
      { what: "모의 계좌번호를 주문 컴퓨터 설정에 넣기", who: "재권님", done: null, how: HAND },
      { what: "주문 컴퓨터마다 슬랙 앱(봇) 만들고 거래 채널에 넣기", who: "재권님", done: null, how: HAND },
      { what: "주문 컴퓨터 한도 — 한 번 · 하루 매수 금액 · 늦은 메시지 초", who: "재권님", done: null, how: HAND },
      { what: "주문 프로그램 실행 파일(윈도우 · 맥) 만들어 깔기", who: "개발2", done: null, how: HAND },
      { what: "서버에 주문 컴퓨터 열쇠 넣기" + (pcs.length ? " — " + esc(pcs.join(" · ")) : ""), who: "개발2", done: pcs.length > 0, how: LIVE },
      { what: "위 「3 룰」 빈 칸 채우기" + (miss.length ? " — " + miss.map((r) => esc(r.name)).join(" · ") : ""), who: "재권님", done: miss.length === 0, how: LIVE },
      { what: "슬랙 보내기 켜기(서버)", who: "재권님 지시", done: !!st.send, how: LIVE },
      { what: "실전 잠금 풀기(주문 컴퓨터) — 모의투자로 다 본 뒤 맨 마지막", who: "재권님 지시", done: null, how: HAND },
    ];
  }
  function stTxt(d) { return d === true ? chip("ok", "됨") : d === false ? chip("warn", "안 됨") : chip("", "모름"); }

  /* ── 1 한눈에 보기 ── */
  function drawGlance() {
    const st = meta || {};
    $("trSwitch").innerHTML =
      '<div class="tr-sw"><div><div class="tr-sw-name">슬랙 보내기</div><div class="tr-sw-where">서버 · 켜야 매수 · 매도 신호가 나감</div></div>' +
        (st.send ? chip("ok", "켜짐") : chip("warn", "꺼짐")) + "</div>" +
      '<div class="tr-sw"><div><div class="tr-sw-name">실전 잠금</div><div class="tr-sw-where">주문 컴퓨터 · 잠겨 있으면 모의투자만</div></div>' +
        chip("", "서버는 모름") + "</div>";

    const ok = [], no = [];
    const miss = missing(), pcs = st.pcs || [];
    if (st.error) no.push("서버 오류 — " + esc(st.error));
    (miss.length ? no : ok).push(miss.length ? "룰 칸 " + miss.length + "개가 비어 있음 — 그날 매수 목록이 안 나감" : "룰 칸 다 참" + (st.settings && st.settings.ver ? " · 룰 판 " + esc(st.settings.ver) : ""));
    (pcs.length ? ok : no).push(pcs.length ? "주문 컴퓨터 " + pcs.length + "대 열쇠 있음 — " + esc(pcs.join(" · ")) : "서버에 주문 컴퓨터 열쇠 없음");
    (st.pcsDropped || []).forEach((d) => no.push("빠진 컴퓨터 " + esc(d.name) + " — " + esc(d.why)));
    (st.send ? ok : no).push(st.send ? "슬랙 보내기 켜짐" : "슬랙 보내기 꺼짐 — 신호가 안 나감");
    ok.push("매매일지 · 룰 저장 칸 — 이 화면에서 바로 씀");
    const me = prepRows().filter((p) => /재권님/.test(p.who) && p.done !== true).map((p) => p.what);
    const col = (cls, h, xs) => '<div class="tr-col ' + cls + '"><h4>' + h + "</h4>" +
      (xs.length ? "<ul>" + xs.map((x) => "<li>" + x + "</li>").join("") + "</ul>" : '<div class="none">없음</div>') + "</div>";
    $("trGlance").innerHTML = col("ok", "됨", ok) + col("no", "안 됨", no) + col("me", "재권님 손 필요", me);
  }

  /* ── 2 흐름 — 그림 한 줄 + 서버가 보내는 것 ── */
  function drawFlow() {
    const st = meta || {};
    const steps = [
      ["단타 판", "종목 고르기", "첫 굳힘 " + tm("firstLock") + " · 차례 위 " + sv(st.pickN) + "종목"],
      ["서버", "서명한 신호", "사라 · 팔아라 · 룰 줄에 컴퓨터마다 다른 열쇠로 서명"],
      ["슬랙", "거래 채널", "서버가 올리고 주문 컴퓨터가 읽음"],
      ["주문 컴퓨터", "검사 · 수량 셈", "서명 · 늦은 메시지 · 같은 번호 · 한도를 본 뒤"],
      ["한국투자", "시장가 주문", "다 안 되면 정한 간격마다 다시"],
      ["주문 컴퓨터", "결과 돌려보냄", "매수가 · 매도가 · 차익 · 세금 → 아래 매매일지"],
    ];
    $("trSteps").innerHTML = steps.map((s) =>
      '<div class="tr-step"><div class="tr-step-who">' + s[0] + '</div><div class="tr-step-name">' + s[1] + '</div><div class="tr-step-what">' + s[2] + "</div></div>").join("");
    $("trSend").innerHTML =
      "<h3>서버가 보내는 것</h3><ol>" +
      "<li>평일 단타 판 첫 굳힘(" + tm("firstLock") + ") 줄 중 굳힘 차례 위 " + sv(st.pickN) + "종목을 슬랙에 한 번 — 종목 코드 · 이름 · 매수금액(단타 판 셈 칸의 첫 굳힘 금액 ÷ 보내는 종목 수) · 굳힘 가격 · 룰 판</li>" +
      "<li>판 매도 룰(손절 · 꺾임 · 고점 · 미달 · 횡보 · 매도 시각 — 단타 판 셈 칸 그대로)에 걸리면 그 종목 「팔아라」 한 번</li>" +
      "<li>룰 칸이 바뀔 때마다 · 매일 " + sv(st.rulesAt) + " 에 서명한 룰 줄 한 번</li></ol>";
  }

  /* ── 3 룰 — 매수 · 매도 따로 · 칸은 열쇠 앞머리(buy · sell)로 가른다 ── */
  function ruleHtml(r) {
    const v = val(r.key);
    return '<div class="tr-rule"><div class="tr-rule-name">' + esc(r.name) + '</div>' +
      '<div class="tr-rule-in"><input inputmode="decimal" data-k="' + esc(r.key) + '" value="' + esc(v === null ? "" : v) + '" aria-label="' + esc(r.name) + '">' +
      '<span class="tr-rule-unit">' + esc(r.unit) + " · " + esc(Number(r.min).toLocaleString("ko-KR")) + "~" + esc(Number(r.max).toLocaleString("ko-KR")) + "</span></div>" +
      '<div class="tr-rule-desc">' + esc(r.desc) + "</div></div>";
  }
  function drawRules() {
    const rs = rules();
    const sell = rs.filter((r) => /^sell/.test(r.key)), buy = rs.filter((r) => !/^sell/.test(r.key));
    $("trRulesBuy").innerHTML = buy.map(ruleHtml).join("");
    $("trRulesSell").innerHTML = sell.map(ruleHtml).join("");
    document.querySelectorAll("#trRulesBuy input, #trRulesSell input").forEach((el) => el.addEventListener("input", onInput));
    check();
  }
  function drawRuleText() {
    $("trBuy").innerHTML = "<ol>" +
      "<li>수량 = 받은 매수금액 ÷ 현재가(소수 버림) · 0주면 「못 삼」</li>" +
      "<li>현재가가 굳힘 가격보다 " + box("buyMaxUpPct") + " 넘게 높으면 안 삼(「못 삼: 오름」)</li>" +
      "<li>시장가로 넣고, 다 안 사졌으면 남은 수량을 " + box("buyRetrySec") + " 마다 다시 시장가 · VI 단일가 중엔 기다림</li>" +
      "<li>그만두는 때 — 현재가가 굳힘 가격보다 " + box("buyMaxUpPct") + " 넘게 오름 · 첫 주문 뒤 " + box("buyMaxMin") + " 지남 → 산 만큼만 들고 감</li></ol>";
    $("trSell").innerHTML = "<ol>" +
      "<li>「팔아라」 를 받으면 그 번호로 실제 체결된 수량만 시장가로(잔고 전체가 아님) · 늦게 온 「팔아라」 도 판다</li>" +
      "<li>안 팔린 수량은 " + box("sellRetrySec") + " 마다 다시 시장가</li>" +
      "<li>장 끝 정리 — " + tm("cleanAt") + " 뒤에도 남으면 장 끝 동시호가에 넣음</li>" +
      "<li>서버가 꺼져 「팔아라」 가 안 와도 " + tm("cleanAt") + " 전에 남은 것을 스스로 시장가로 판다</li></ol>";
    $("trFail").innerHTML = "<h3>못 사고 못 팔 때</h3><ul>" +
      "<li>못 삼 — 0주 · 오름 · 한도 · 시간 지남이면 그 까닭을 결과 줄로 보내고 매매일지에 남김</li>" +
      "<li>못 팖 — 장 끝 동시호가에서도 남으면 「못 팖 · 남은 수량」 을 보내고 다음 거래일 " + tm("reopenAt") + " 다시</li>" +
      "<li>주문 응답을 못 받음 — 다시 넣지 않고 「확인 필요」 로 멈춤(아래 「4 안전장치」)</li></ul>";
  }

  /* ── 4 안전장치 ── */
  function drawSafe() {
    const it = (name, what, where) => "<li><b>" + name + "</b> — " + what + ' <span class="where">· ' + where + "</span></li>";
    $("trSafe").innerHTML = "<ul>" +
      it("서명", "모든 메시지에 서명 · 서명이 안 맞는 글은 주문 · 일지를 못 움직임", "서버가 서명 · 주문 컴퓨터가 확인") +
      it("컴퓨터마다 열쇠", "열쇠가 컴퓨터마다 달라 한 대가 새도 다른 컴퓨터 이름으로 못 보냄", "서버 비밀 파일 · 주문 컴퓨터 설정") +
      it("실전 잠금", "실전 계좌는 잠금 칸을 풀어야 켜짐 · 풀지 않으면 모의투자만", "주문 컴퓨터 설정 · 재권님 지시 뒤에만") +
      it("한도", "한 번 · 하루 매수 금액 한도를 서버가 보낸 금액보다 먼저 봄 · 비어 있으면 안 삼", "주문 컴퓨터 설정") +
      it("늦은 메시지", "매수 신호가 정한 초를 넘겨 오면 버림(슬랙 서버 시각 기준) · 매도는 늦어도 팖", "주문 컴퓨터 설정") +
      it("같은 번호 한 번", "주문 전에 「이 번호 주문함」 을 먼저 디스크에 적어 두 번 사지 않음 · 다시 넣기 전에 앞 주문 취소를 확인", "주문 컴퓨터") +
      it("「확인 필요」 멈춤", "주문 응답을 못 받았거나 주문 중에 꺼졌으면 그 줄을 멈추고 다시 안 넣음 · 증권사 앱에서 보고 정리", "주문 컴퓨터") +
      it("기록", "단계마다 로그(받음 · 기록 · 요청 · 응답 · 체결 · 까닭) · 열쇠 · 계좌번호는 가림", "주문 컴퓨터") +
      "</ul>";
  }

  /* ── 5 준비할 것 ── */
  function drawPrep() {
    $("trPrep").innerHTML = "<table><thead><tr><th>할 것</th><th>누가</th><th>됐나</th><th>어디서 안 값</th></tr></thead><tbody>" +
      prepRows().map((p) => "<tr><td>" + p.what + "</td><td>" + esc(p.who) + '</td><td class="st">' + stTxt(p.done) + "</td><td>" + esc(p.how) + "</td></tr>").join("") +
      '</tbody></table><div class="note">「모름」 줄은 주문 컴퓨터 설정에만 있어 서버가 알 수 없습니다 — 되면 말씀해 주시면 적은 날과 함께 고칩니다</div>';
  }

  function drawAll() { drawGlance(); drawFlow(); drawRuleText(); drawSafe(); drawPrep(); }

  function onInput(e) {
    const k = e.target.dataset.k, t = e.target.value.trim();
    doc[k] = t === "" ? null : Number(t);
    dirty = true;
    check();
    drawAll();
  }

  function check() {
    let ok = true;
    document.querySelectorAll("#trRulesBuy input, #trRulesSell input").forEach((el) => {
      const r = rules().find((x) => x.key === el.dataset.k);
      const t = el.value.trim();
      const bad = t !== "" && !valid(r, t);
      el.classList.toggle("bad", bad);
      if (bad) ok = false;
    });
    $("trSave").disabled = !dirty || !ok;
    $("trMsg").textContent = !ok ? "범위 밖 칸이 있어 저장할 수 없습니다" : dirty ? "저장 전 — 저장하면 룰 판이 바뀌고 주문 컴퓨터에 새 룰이 갑니다(보내기 켜진 때)" : "";
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
      drawRules(); drawAll(); drawLog(j.data || []);
      $("trMsg").textContent = "";
    }).catch(() => {
      $("trSwitch").innerHTML = chip("warn", "서버 값을 못 받음 — 자동 매매 칸을 그릴 수 없습니다");
      $("trMsg").textContent = "";
    });
  }

  function save() {
    const data = {};
    rules().forEach((r) => { data[r.key] = val(r.key) === null ? null : Number(val(r.key)); });
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
