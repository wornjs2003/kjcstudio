# -*- coding: utf-8 -*-
"""주문 컴퓨터 창 — 상태 · 오늘 일감 · 로그 보기(날짜 · 번호 · 종목으로 고름) · 로그 내보내기 (2026-11-23 · 개발2).

설정은 이 프로그램 옆 config.json 하나(견본 config.example.json) — 열쇠 · 계좌는 그 파일에만 · 실행 파일 안에 안 넣는다.
멈춤 단추는 없다 — 재권님 「매수와 매도를 종목별로 한번씩만 걸거니 멈춤은 없어도 돼」(11-23). 끄려면 창을 닫는다(넣은 주문은 증권사에 남는다).
"""
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

from . import core
from .kis import Kis
from .slack import READ_SEC, Slack

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # 윈도우 콘솔 cp949 에서 죽지 않게(「한글을 출력하는 파이썬 도구에는 이 두 줄」)


def home():
    """실행 파일이면 그 옆(맥은 .app 묶음 옆) · 아니면 holdings/trader."""
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.dirname(sys.executable)
    if d.endswith(".app/Contents/MacOS"):                           # 맥 묶음 안쪽이 아니라 묶음 옆에 config.json 을 둔다
        d = os.path.dirname(os.path.dirname(os.path.dirname(d)))
    return d


REQUIRED = ("name", "sign_key", "late_sec", "max_order_won", "max_day_won")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    miss = [k for k in REQUIRED if c.get(k) in (None, "")] + [k for k in ("bot_token", "channel_id") if not (c.get("slack") or {}).get(k)] + \
        [k for k in ("env", "app_key", "app_secret", "account8") if not (c.get("kis") or {}).get(k)]
    if miss:
        raise ValueError("설정 칸이 비었습니다 — " + ", ".join(miss))
    if (c.get("kis") or {}).get("env") == "real" and c.get("real_ok") is not True:
        raise ValueError("실전 계좌는 real_ok 를 true 로 바꿔야 켜집니다 — 재권님 지시 뒤에만(되돌릴 수 없는 주문)")
    return c


class Runner(threading.Thread):
    """읽기(READ_SEC) · tick(1초) 를 도는 일꾼."""

    def __init__(self, eng, slack, log):
        super().__init__(daemon=True)
        self.eng, self.slack, self.log = eng, slack, log
        self.alive = True
        self.status = "시작"

    def run(self):
        last_read = 0.0
        while self.alive:
            try:
                if time.time() - last_read >= READ_SEC:
                    last_read = time.time()
                    msgs, nxt = self.slack.read_since(self.eng.st.get("lastTs"))
                    for ts, text in msgs:
                        self.eng.on_message(text, ts)
                    if not msgs and self.eng.st.get("lastTs") is None:
                        self.eng.st["lastTs"] = nxt
                        self.eng.save()
                self.eng.tick()
                self.status = "도는 중 · %s" % core.now_kst().strftime("%H:%M:%S")
            except Exception as e:
                self.status = "오류 — %s" % core.mask(e)
                self.log.put("일꾼", "오류 %s: %s" % (type(e).__name__, e), level="error")
                time.sleep(3)
            time.sleep(1)


class App:
    def __init__(self, root):
        self.root = root
        h = home()
        self.cfg_path = os.path.join(h, "config.json")
        self.state_path = os.path.join(h, "state.json")
        self.log = core.Log(os.path.join(h, "logs"))
        root.title("KJC 주문 컴퓨터")
        root.geometry("1100x700")
        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        self.v_status = tk.StringVar(value="설정 읽는 중…")
        ttk.Label(top, textvariable=self.v_status, font=("", 13, "bold")).pack(side="left")
        ttk.Button(top, text="로그 내보내기", command=self.export).pack(side="right")
        mid = ttk.Frame(root, padding=(8, 0))
        mid.pack(fill="x")
        self.jobs = ttk.Treeview(mid, columns=("jid", "code", "name", "buy", "sell", "why"), show="headings", height=6)
        for c, t, w in (("jid", "번호", 60), ("code", "종목", 80), ("name", "이름", 140), ("buy", "매수(체결/목표)", 140), ("sell", "매도(체결)", 120), ("why", "까닭", 480)):
            self.jobs.heading(c, text=t)
            self.jobs.column(c, width=w, anchor="w")
        self.jobs.pack(fill="x")
        flt = ttk.Frame(root, padding=8)
        flt.pack(fill="x")
        self.v_day = tk.StringVar(value=core.now_kst().strftime("%Y%m%d"))
        self.v_jid, self.v_code, self.v_err = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        for lab, var, w in (("날짜", self.v_day, 10), ("번호", self.v_jid, 6), ("종목", self.v_code, 8)):
            ttk.Label(flt, text=lab).pack(side="left")
            ttk.Entry(flt, textvariable=var, width=w).pack(side="left", padx=(2, 10))
        ttk.Checkbutton(flt, text="오류 · 경고만", variable=self.v_err).pack(side="left")
        ttk.Button(flt, text="로그 보기", command=self.show_log).pack(side="left", padx=8)
        self.text = tk.Text(root, wrap="none", font=("Menlo" if sys.platform == "darwin" else "Consolas", 11))
        self.text.tag_configure("error", foreground="#c0392b")
        self.text.tag_configure("warn", foreground="#b9770e")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.runner = None
        self.start()
        self.refresh()

    def start(self):
        try:
            c = load_config(self.cfg_path)
        except FileNotFoundError:
            self.v_status.set("config.json 이 없습니다 — config.example.json 을 복사해 채워 주십시오")
            return
        except Exception as e:
            self.v_status.set("설정 오류 — %s" % core.mask(e))
            return
        k = Kis(c["kis"], os.path.join(home(), ".kis-token.json"))
        s = Slack(c["slack"]["bot_token"], c["slack"]["channel_id"])
        eng = core.Engine(c, k, s, self.log, self.state_path)
        self.log.prune()
        self.log.put("시작", "켜짐 · 이름 %s · 증권사 %s(%s)" % (c["name"], "한국투자", c["kis"]["env"]))
        self.runner = Runner(eng, s, self.log)
        self.runner.start()

    def refresh(self):
        if self.runner:
            st = self.runner.eng.st
            r = st.get("rules") or {}
            self.v_status.set("%s · 룰 판 %s" % (self.runner.status, r.get("ver") or "아직 없음"))
            self.jobs.delete(*self.jobs.get_children())
            for jid, j in sorted(st["jobs"].items(), key=lambda x: x[1]["got"], reverse=True)[:30]:
                b, s = j["buy"], j["sell"]
                why = b.get("hold") or s.get("hold") or (s["why"] or s["pending"] or b["why"] or "")
                self.jobs.insert("", "end", values=(jid, j["code"], j["name"], "%d/%s" % (b["filled"], b.get("want", "-")), s["filled"], why))
        self.root.after(1000, self.refresh)

    def show_log(self):
        rows = self.log.read(self.v_day.get().strip(), self.v_jid.get().strip() or None, self.v_code.get().strip() or None)
        if self.v_err.get():
            rows = [r for r in rows if r["level"] in ("error", "warn")]
        self.text.delete("1.0", "end")
        for r in rows:
            self.text.insert("end", "%s  %-6s %-4s %-7s %s\n" % (r["at"], r["step"], r.get("jid") or "", r.get("code") or "", r["text"]),
                             r["level"] if r["level"] in ("error", "warn") else ())

    def export(self):
        day = self.v_day.get().strip()
        out = os.path.join(home(), "로그-%s.zip" % day)
        self.log.export(day, self.state_path, out)
        self.v_status.set("내보냄 — %s" % out)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
