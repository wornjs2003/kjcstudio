# -*- coding: utf-8 -*-
"""주문 컴퓨터의 몸통 — 슬랙 메시지 확인 · 매수 · 매도 · 결과 보내기 · 기록 (2026-11-23 · 개발2).

재권님이 정하신 것(11-23 · 카드 「자동 매수」)
    서버(holdings/server/trade_signal.py)가 슬랙에 BUY · SELL · RULES 를 보내면 이 컴퓨터가 받아 자기 계좌로 사고판다 · 결과를 RESULT 로 돌려 보낸다
    「주물할때 시가 / 팔때도 마찬가지」 → 매수 · 매도 즉시 시장가 · 「다 못사지면 다시 시가로 산다」 → 안 된 수량은 룰 간격마다 다시 시장가
    「매수와 매도를 종목별로 한번씩만 걸거니 멈춤은 없어도 돼」 → 멈춤 단추 없음 · 같은 번호 한 번
    「api에 룰 개선 가능하도록 () 만들어놔」 → 룰 값은 서버가 서명해 보낸 RULES 만 따름(이 컴퓨터에서 안 고침)
    「매매 컴퓨터에 매수매매 에 대한 로그를 남기고 그 로그를 보면서 디버깅 가능하도록」 → 단계마다 로그 한 줄(Log)
    메시지 꼴 · 서명은 서버 파일 머리 글 한 곳 그대로 — 바꾸면 둘을 함께 바꾼다

크로스체크(개념정의 · qa 11-23)에서 받은 것
    같은 번호는 주문 **전에** 디스크에 먼저 적음 · 팔 수량은 그 번호로 체결된 수량만(잔고 전체 아님) · 늦은 메시지 버림은 BUY 만(SELL 은 늦어도 팖)
    시계는 슬랙 서버 시각(ts)과 보낸 시각 차이로 · 매수 중 SELL 이 오면 남은 매수부터 취소 · 서버가 꺼져도 cleanAt 에 스스로 정리
    주문을 다시 넣기 전에 앞 주문을 취소하고 취소가 된 것을 본 뒤에 넣음(두 번 사지 않게) · 주문을 넣는 중에 꺼졌으면 다시 켤 때 그 줄은 「확인 필요」 로 멈춤
"""
import hashlib
import hmac
import json
import os
import re
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

from .kis import KisError

KST = timezone(timedelta(hours=9))
RULE_KEYS = ("buyRetrySec", "buyMaxUpPct", "buyMaxMin", "sellRetrySec", "cleanAt", "reopenAt")
CLOSE_AT = "15:30"             # 정규장 끝 — 서버 룰 줄에 closeAt 이 없을 때만(옛 서버) · 이 뒤로는 시장가 주문을 안 넣는다(qa 11-23 ③) · 다음 거래일 reopenAt 에 다시


def hhmm(v):
    """시각 「HHMM」(서버 룰 줄 · cleanAt=1520) · 「HH:MM」 둘 다 「HH:MM」 으로 — 글자로 견주므로 꼴이 갈리면 15:00 부터 걸린다(qa 11-23 ①)."""
    v = str(v).strip()
    return v if ":" in v else "%s:%s" % (v[:2], v[2:4])
_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_MASK = re.compile(r"(appkey|appsecret|app_key|app_secret|token|authorization|bot_token|sign_key|CANO|cano)(\W{1,4})([^\s\"',}]{4,})", re.I)


def now_kst():
    return datetime.now(KST)


def sign(key, body):
    return hmac.new(key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def mask(text):
    """열쇠 · 토큰 · 계좌번호는 뒤 넷만(qa 15)."""
    return _MASK.sub(lambda m: m.group(1) + m.group(2) + "…" + m.group(3)[-4:], str(text))


def write_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Log:
    """단계마다 한 줄(JSON) — 날짜마다 파일 하나 · 번호 · 종목 · 단계 · 글. 열쇠 · 계좌는 가림."""

    def __init__(self, folder, keep_days=60):
        self.folder = folder
        self.keep_days = keep_days
        os.makedirs(folder, exist_ok=True)
        self._lock = threading.Lock()
        self.listeners = []

    def path(self, day):
        return os.path.join(self.folder, "%s.jsonl" % day)

    def put(self, step, text, jid=None, code=None, level="info", **extra):
        now = now_kst()
        row = {"at": now.strftime("%Y-%m-%d %H:%M:%S"), "step": step, "jid": jid, "code": code, "level": level, "text": mask(text)}
        for k, v in extra.items():
            row[k] = mask(v) if isinstance(v, str) else v
        with self._lock:
            with open(self.path(now.strftime("%Y%m%d")), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        for fn in list(self.listeners):
            try:
                fn(row)
            except Exception:
                pass
        return row

    def read(self, day, jid=None, code=None):
        out = []
        try:
            with open(self.path(day), encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if (jid is None or str(r.get("jid")) == str(jid)) and (code is None or r.get("code") == code):
                        out.append(r)
        except FileNotFoundError:
            pass
        return out

    def export(self, day, state_path, out_path):
        """그날 로그 + 상태 파일을 zip 하나로 — 여기 보내 되짚게(qa · 재권님 「로그를 보면서 디버깅」)."""
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(self.path(day)):
                z.write(self.path(day), "log-%s.jsonl" % day)
            if os.path.exists(state_path):
                with open(state_path, encoding="utf-8") as f:
                    z.writestr("state.json", mask(f.read()))
        return out_path

    def prune(self):
        cut = (now_kst() - timedelta(days=self.keep_days)).strftime("%Y%m%d")
        for n in os.listdir(self.folder):
            if n.endswith(".jsonl") and n[:8] < cut:
                os.remove(os.path.join(self.folder, n))


class Engine:
    """메시지를 받아 일감(job)을 만들고 tick 마다 증권사에 주문 · 확인한다. 증권사(kis) · 슬랙(slack) · 시계(clock)는 갈아 끼울 수 있다(시험)."""

    def __init__(self, cfg, kis, slack, log, state_path, clock=now_kst):
        self.cfg, self.kis, self.slack, self.log, self.state_path, self.clock = cfg, kis, slack, log, state_path, clock
        self.name = cfg["name"]
        self.key = cfg["sign_key"]
        self._lock = threading.RLock()
        self.st = {"seen": {}, "jobs": {}, "rules": None, "lastTs": None, "spent": {}}
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                self.st.update(json.load(f))
        for jid, j in self.st["jobs"].items():                       # 주문을 넣는 중에 꺼졌으면 — 넣었는지 모름 · 두 번 안 사게 멈춤(크로스체크 A · qa 8)
            for side in ("buy", "sell"):
                if j[side].get("placing"):
                    j[side]["placing"] = False
                    j[side]["hold"] = "확인 필요 — 주문을 넣는 중에 프로그램이 꺼졌음(증권사 앱에서 주문 · 체결을 보고 정리)"
                    self.log.put("되살림", j[side]["hold"], jid, j["code"], "error", side=side)
        self.save()

    # ── 저장 ─────────────────────────────
    def save(self):
        with self._lock:
            write_json_atomic(self.state_path, self.st)

    # ── 메시지 ───────────────────────────
    def _verify(self, line):
        """「이름=서명;…」 묶음에서 내 이름 칸을 내 열쇠로 본다 → 서명 뺀 글 | None."""
        body, _, sigs = line.rpartition("|")
        mine = dict(x.split("=", 1) for x in sigs.split(";") if "=" in x).get(self.name)
        return body if body and mine and hmac.compare_digest(sign(self.key, body), mine.strip().lower()) else None

    def on_message(self, text, ts):
        """슬랙 메시지 하나(ts — 슬랙 서버 시각 초) — BUY · SELL · RULES 줄만 본다."""
        for line in (text or "").splitlines():
            line = line.strip()
            if not re.match(r"^(BUY|SELL|RULES)\|", line):
                continue
            body = self._verify(line)
            if body is None:
                self.log.put("받음", "서명 틀림 — 버림 · " + line[:60], level="warn")
                continue
            p = body.split("|")
            try:
                {"BUY": self._buy_msg, "SELL": self._sell_msg, "RULES": self._rules_msg}[p[0]](p, float(ts))
            except Exception as e:
                self.log.put("받음", "꼴이 틀림 — %s · %s" % (type(e).__name__, line[:60]), level="warn")
        with self._lock:
            if ts and (self.st["lastTs"] is None or float(ts) > float(self.st["lastTs"])):
                self.st["lastTs"] = str(ts)
            self.save()

    def _sent_epoch(self, s):
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=KST).timestamp()

    def _rules_msg(self, p, ts):
        _, ver, kv, _sent = p[:4]
        vals = {}
        for x in kv.split(";"):
            k, _, v = x.partition("=")
            if k in RULE_KEYS:
                vals[k] = hhmm(v) if k in ("cleanAt", "reopenAt") else float(v)
            elif k == "closeAt":                                     # 고를 칸 — 그날 정규장 끝(수능 날 밀림) · 없으면 CLOSE_AT
                vals[k] = hhmm(v)
            elif k == "openDay":                                     # 고를 칸 — 그날이 거래일이면 그 날짜(「-」 휴장 · 「?」 못 잼)
                vals[k] = v
        cur = self.st.get("rules") or {}
        if cur.get("ver") and ver < cur["ver"]:
            self.log.put("룰", "옛 룰 판 %s — 지금 %s 그대로" % (ver, cur["ver"]))
            return
        if any(k not in vals for k in RULE_KEYS):
            self.log.put("룰", "룰 칸이 모자람 — 안 씀 · %s" % kv, level="warn")
            return
        with self._lock:
            self.st["rules"] = {"ver": ver, "gotDay": self.clock().date().isoformat(), **vals}
            self.save()
        self.log.put("룰", "룰 판 %s 받음 · %s" % (ver, kv))

    def _buy_msg(self, p, ts):
        _, jid, code, name, amount, lock_px, ver, sent = p[:8]
        late = abs(ts - self._sent_epoch(sent))
        if late > float(self.cfg["late_sec"]):                         # 늦은 메시지 버림은 BUY 만 · 슬랙 서버 시각으로 셈(qa 10 · 크로스체크 C · ④)
            self.log.put("받음", "늦은 매수 신호 버림 — 보낸 뒤 %.0f초" % late, jid, code, "warn")
            return
        with self._lock:
            if ("B" + jid) in self.st["seen"]:
                self.log.put("받음", "같은 번호 매수 신호 — 버림", jid, code)
                return
            self.st["seen"]["B" + jid] = self.clock().isoformat()
            self.st["jobs"][jid] = {"code": code, "name": name, "amount": int(amount), "lockPx": float(lock_px), "ruleVer": ver,
                                   "got": self.clock().isoformat(),
                                   "buy": {"orders": [], "filled": 0, "cost": 0.0, "done": False, "why": None, "start": None, "next": 0},
                                   "sell": {"orders": [], "filled": 0, "proceeds": 0.0, "done": False, "why": None, "pending": None, "next": 0},
                                   "resultSent": False}
            self.save()                                              # 먼저 적고 → 주문(크로스체크 A)
        self.log.put("받음", "매수 신호 — %s %s · 금액 %s원 · 굳힘 가격 %s · 룰 판 %s" % (name, code, amount, lock_px, ver), jid, code)

    def _sell_msg(self, p, ts):
        _, jid, code, name, why, _sent = p[:6]                       # SELL 은 늦어도 판다(크로스체크 C)
        with self._lock:
            j = self.st["jobs"].get(jid)
            if ("S" + jid) in self.st["seen"]:
                self.log.put("받음", "같은 번호 매도 신호 — 버림", jid, code)
                return
            self.st["seen"]["S" + jid] = self.clock().isoformat()
            if not j or j["code"] != code:
                self.log.put("받음", "산 적 없는 번호의 매도 신호 — 무시", jid, code)
                self.save()
                return
            j["sell"]["pending"] = why
            self.save()
        self.log.put("받음", "매도 신호 — 까닭 %s" % why, jid, code)

    # ── 주문 한 번(먼저 적고 → 넣고 → 번호 적기) ─────────
    def _place(self, jid, j, side, qty):
        s = j[side]
        s["placing"] = True
        self.save()
        try:
            r = self.kis.order_market(j["code"], qty, side)
        except KisError as e:                                          # 증권사가 거절했다고 답함 — 안 들어감 · 다음 바퀴에 다시
            s["placing"] = False
            self.save()
            self.log.put("주문", "%s 시장가 %d주 — 증권사 거절 %s" % ("매수" if side == "buy" else "매도", qty, e), jid, j["code"], "error")
            return None
        except Exception as e:                                         # 시간 초과 · 연결 끊김 — 들어갔는지 모름 · 두 번 안 넣게 멈춤(qa 11-23 ②)
            s["placing"] = False
            s["hold"] = "확인 필요 — %s 시장가 %d주 주문의 응답을 못 받음(%s) · 증권사 앱에서 주문 · 체결을 보고 정리" % (
                "매수" if side == "buy" else "매도", qty, type(e).__name__)
            self.save()
            self.log.put("주문", s["hold"], jid, j["code"], "error", side=side)
            return None
        s["placing"] = False
        s["orders"].append({"odno": r["odno"], "orgno": r.get("orgno"), "qty": qty, "filled": 0, "amt": 0.0, "open": True})
        self.save()
        self.log.put("주문", "%s 시장가 %d주 — 주문번호 %s" % ("매수" if side == "buy" else "매도", qty, r["odno"]), jid, j["code"])
        return r

    def _refresh(self, jid, j, side):
        """그 쪽 주문들의 체결을 증권사에 물어 filled · 금액을 다시 셈 → 열린 주문 | None."""
        s, opn = j[side], None
        for o in s["orders"]:
            if not o["open"]:
                continue
            q = self.kis.order_status(o["odno"], j["code"])
            if q is None:
                self.log.put("확인", "주문번호 %s 를 증권사 조회에서 못 찾음" % o["odno"], jid, j["code"], "warn")
                opn = o
                continue
            if q["filled"] != o["filled"]:
                self.log.put("체결", "주문번호 %s — 체결 %d/%d주 · 평균 %s" % (o["odno"], q["filled"], o["qty"], q["avg"]), jid, j["code"])
            o["filled"], o["amt"], o["open"] = q["filled"], q["filled"] * (q["avg"] or 0), q["open"]
            if o["open"]:
                opn = o
        s["filled"] = sum(o["filled"] for o in s["orders"])
        s["cost" if side == "buy" else "proceeds"] = sum(o["amt"] for o in s["orders"])
        self.save()
        return opn

    def _cancel(self, jid, j, o):
        try:
            self.kis.cancel(o["odno"], o.get("orgno"), j["code"])
            self.log.put("취소", "주문번호 %s 남은 것 취소 요청" % o["odno"], jid, j["code"])
        except Exception as e:
            self.log.put("취소", "주문번호 %s 취소 오류 %s" % (o["odno"], e), jid, j["code"], "error")

    # ── tick ─────────────────────────────
    def tick(self):
        R = self.st.get("rules")
        now = self.clock()
        hm = now.strftime("%H:%M")
        for jid, j in list(self.st["jobs"].items()):
            if j.get("resultSent"):
                continue
            if j["buy"].get("hold") or j["sell"].get("hold"):
                continue
            if not R:
                if not j.get("noRulesLogged"):
                    j["noRulesLogged"] = True
                    self.log.put("기다림", "룰을 아직 못 받음 — 주문 안 함", jid, j["code"], "warn")
                continue
            if not j["sell"]["pending"] and j["buy"]["filled"] > 0 and hm >= R["cleanAt"] and j["got"][:10] == now.date().isoformat():
                j["sell"]["pending"] = "스스로 정리"                    # 서버가 꺼져 SELL 이 안 와도(qa 덧)
                self.log.put("매도", "정리 시각 %s — 스스로 매도" % R["cleanAt"], jid, j["code"])
            if not j["buy"]["done"]:
                self._buy_step(jid, j, R, now)
            if j["buy"]["done"] and j["sell"]["pending"] and not j["sell"]["done"]:
                self._sell_step(jid, j, R, now)
            if j["buy"]["done"] and (j["buy"]["filled"] == 0 or j["sell"]["done"]) and not j["resultSent"]:
                self._result(jid, j, now)
        self.save()

    def _buy_step(self, jid, j, R, now):
        b = j["buy"]
        t = now.timestamp()                                            # 시계는 갈아 끼울 수 있게(시험)
        if b["orders"] and t < b["next"]:
            return
        if j["sell"]["pending"]:                                      # 매수 중 SELL — 남은 매수 취소 → 산 것만 판다(qa 3)
            o = self._refresh(jid, j, "buy") if b["orders"] else None
            if o:
                self._cancel(jid, j, o)
                self._refresh(jid, j, "buy")
            b["done"], b["why"] = True, "매도 신호로 매수 끝"
            self.log.put("매수", "매도 신호가 와서 매수 그만 — 산 %d주" % b["filled"], jid, j["code"])
            return
        price = self.kis.price(j["code"])
        cap = j["lockPx"] * (1 + R["buyMaxUpPct"] / 100.0)
        if not b["orders"]:
            if price is None:
                self.log.put("매수", "현재가를 못 받음 — 다음에 다시", jid, j["code"], "warn")
                b["next"] = t + R["buyRetrySec"]
                return
            if price > cap:
                b["done"], b["why"] = True, "못 삼: 현재가 %s 가 굳힘 가격 %s 보다 %.2f%% 넘게 높음" % (price, j["lockPx"], R["buyMaxUpPct"])
                self.log.put("매수", b["why"], jid, j["code"], "warn")
                return
            qty = self._cap_qty(int(j["amount"] // price), price, now)
            if qty <= 0:
                b["done"], b["why"] = True, "못 삼: 0주(금액 %s · 현재가 %s · 이 컴퓨터 한도)" % (j["amount"], price)
                self.log.put("매수", b["why"], jid, j["code"], "warn")
                return
            b["start"], b["want"] = t, qty
            if self._place(jid, j, "buy", qty):
                self._spend(now, qty * price)
            b["next"] = t + R["buyRetrySec"]
            return
        o = self._refresh(jid, j, "buy")
        left = b["want"] - b["filled"]
        if left <= 0:
            b["done"], b["why"] = True, "다 삼"
            self.log.put("매수", "다 삼 — %d주 · %s원" % (b["filled"], round(b["cost"])), jid, j["code"])
            return
        stop = None
        if price is not None and price > cap:
            stop = "그만: 현재가 %s 가 굳힘 가격보다 %.2f%% 넘게 오름" % (price, R["buyMaxUpPct"])
        elif t - b["start"] > R["buyMaxMin"] * 60:
            stop = "그만: 첫 주문 뒤 %d분 지남" % R["buyMaxMin"]
        if stop:
            if o:
                self._cancel(jid, j, o)
                self._refresh(jid, j, "buy")
            b["done"], b["why"] = True, stop + " · 산 %d주" % b["filled"]
            self.log.put("매수", b["why"], jid, j["code"], "warn")
            return
        if o:                                                         # 앞 주문을 먼저 취소하고, 다음 바퀴에 닫힌 것을 본 뒤 다시 넣음(두 번 안 사게)
            self._cancel(jid, j, o)
            b["next"] = t + 1
            return
        self.log.put("매수", "다 안 사짐 — 남은 %d주 다시 시장가" % left, jid, j["code"])
        if self._place(jid, j, "buy", left) and price:
            self._spend(now, left * price)
        b["next"] = t + R["buyRetrySec"]

    def _sell_step(self, jid, j, R, now):
        s, b = j["sell"], j["buy"]
        t = now.timestamp()                                            # 시계는 갈아 끼울 수 있게(시험)
        hm = now.strftime("%H:%M")
        later = j["got"][:10] < now.date().isoformat()
        # 그날이 거래일인가 — 서버가 그날 보낸 룰 줄의 openDay(휴장일 표) · 없거나 옛 날짜면 주말만 가른다(개념정의 덧 ③)
        od = R.get("openDay")
        if od and od not in ("?",) and len(od) == 8 and od == now.strftime("%Y%m%d"):
            open_day = True
        elif od == "-" and R.get("gotDay") == now.date().isoformat():
            open_day = False
        else:
            open_day = now.weekday() < 5
        if hm >= (R.get("closeAt") or CLOSE_AT) or (later and (hm < R["reopenAt"] or not open_day)):   # 장 뒤 · 다음 날 장 전 · 휴장일 — 넣지 않는다(qa 11-23 ③)
            if s.get("waitDay") != now.date().isoformat():
                s["waitDay"] = now.date().isoformat()
                self.log.put("매도", "장 밖 — 다음 거래일 %s 에 남은 것을 팖" % R["reopenAt"], jid, j["code"])
            return
        if s["orders"] and t < s["next"]:
            return
        if s["orders"]:
            o = self._refresh(jid, j, "sell")
        else:
            o = None
        left = b["filled"] - s["filled"]                              # 그 번호로 체결된 수량만(잔고 전체 아님 · 크로스체크 B)
        if left <= 0:
            s["done"], s["why"] = True, "매도 끝"
            self.log.put("매도", "다 팖 — %d주 · %s원" % (s["filled"], round(s["proceeds"])), jid, j["code"])
            return
        if o:
            self._cancel(jid, j, o)
            s["next"] = t + 1
            return
        if s["orders"]:
            self.log.put("매도", "다 안 팔림 — 남은 %d주 다시 시장가" % left, jid, j["code"])
        self._place(jid, j, "sell", left)
        s["next"] = t + R["sellRetrySec"]

    def _cap_qty(self, qty, price, now):
        """이 컴퓨터 한도(한 번 · 하루 금액 · 원) — 서버 금액보다 먼저(돈이 실제로 막히는 자리)."""
        one, day = self.cfg.get("max_order_won"), self.cfg.get("max_day_won")
        if not one or not day:
            return 0                                                  # 한도 칸이 비면 안 삼
        spent = self.st["spent"].get(now.strftime("%Y%m%d"), 0)
        room = min(one, day - spent)
        return max(0, min(qty, int(room // price)))

    def _spend(self, now, won):
        d = now.strftime("%Y%m%d")
        self.st["spent"][d] = self.st["spent"].get(d, 0) + won
        self.save()

    def _result(self, jid, j, now):
        b, s = j["buy"], j["sell"]
        qty = b["filled"]
        bpx = round(b["cost"] / qty) if qty else "-"
        spx = round(s["proceeds"] / s["filled"]) if s["filled"] else "-"
        tax_pct = self.cfg.get("sell_tax_pct")
        tax = round(s["proceeds"] * tax_pct / 100) if (tax_pct is not None and s["filled"]) else ("0" if not s["filled"] else "-")
        profit = round(s["proceeds"] - b["cost"] - (tax if isinstance(tax, (int, float)) else 0)) if qty else 0
        why = (b["why"] if not qty else s["why"] or "매도 끝").replace("|", " ").replace("\n", " ")[:100]
        body = "RESULT|%s|%s|%s|%s|%s|%d|%s|%s|%s|%s" % (self.name, jid, j["code"], bpx, spx, qty, profit, tax, now.strftime("%Y%m%d%H%M%S"), why)
        try:
            self.slack.post(body + "|" + sign(self.key, body))
        except Exception as e:
            self.log.put("결과", "결과 못 보냄 — %s · 다음에 다시" % e, jid, j["code"], "error")
            return
        j["resultSent"] = True
        self.save()
        self.log.put("결과", "결과 보냄 — " + body, jid, j["code"])
