# -*- coding: utf-8 -*-
"""주문 컴퓨터 몸통 시험 — 가짜 증권사 · 가짜 슬랙 · 가짜 시계 (qa 크로스체크 11-23 의 시험 목록).
돌리기: python3 -m unittest discover -s holdings/trader/tests  (holdings/trader 폴더 기준 · 진짜 증권사 · 슬랙을 안 부름)"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kjc_trader import core  # noqa: E402

KEY = "a" * 64


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def go(self, sec):
        self.t += timedelta(seconds=sec)


class FakeKis:
    """주문마다 채울 양을 정해 둔다 — fill[side] 목록에서 하나씩 꺼냄(없으면 다 채움)."""

    def __init__(self, price=1000.0):
        self.px = price
        self.orders, self.calls = {}, []
        self.fill = {"buy": [], "sell": []}
        self.fail_order = False
        self.n = 0

    def price(self, code):
        return self.px

    def order_market(self, code, qty, side):
        self.calls.append(("order", side, qty))
        if self.fail_order:
            raise RuntimeError("거절")
        self.n += 1
        f = self.fill[side].pop(0) if self.fill[side] else qty
        od = "%05d" % self.n
        self.orders[od] = {"qty": qty, "filled": min(f, qty), "open": f < qty, "avg": self.px}
        return {"odno": od, "orgno": "91252"}

    def cancel(self, odno, orgno, code):
        self.calls.append(("cancel", odno))
        self.orders[odno]["open"] = False

    def order_status(self, odno, code):
        o = self.orders.get(odno)
        return None if o is None else {"filled": o["filled"], "avg": o["avg"], "open": o["open"]}


class FakeSlack:
    def __init__(self):
        self.posts = []

    def post(self, text):
        self.posts.append(text)


def line(kind, body, key=KEY, name="pc1"):
    b = kind + "|" + body
    return b + "|" + name + "=" + core.sign(key, b)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.clock = Clock(datetime(2026, 11, 24, 9, 5, 10, tzinfo=core.KST))
        self.kis, self.slack = FakeKis(), FakeSlack()
        self.cfg = {"name": "pc1", "sign_key": KEY, "late_sec": 60, "max_order_won": 20000000, "max_day_won": 50000000, "sell_tax_pct": 0.2}
        self.log = core.Log(os.path.join(self.d, "logs"))
        self.e = self.mk()

    def mk(self):
        return core.Engine(self.cfg, self.kis, self.slack, self.log, os.path.join(self.d, "state.json"), clock=self.clock)

    def ts(self, dsec=0):
        return self.clock.t.timestamp() + dsec

    def sent(self):
        return self.clock.t.strftime("%Y%m%d%H%M%S")

    def rules(self):
        self.e.on_message(line("RULES", "v1|buyRetrySec=3;buyMaxUpPct=2;buyMaxMin=5;sellRetrySec=3;cleanAt=15:20;reopenAt=09:00|" + self.sent()), self.ts())

    def buy(self, jid="1", amount=1000000, lock=1000, dsec=1):
        self.e.on_message(line("BUY", "%s|005930|삼성|%d|%d|v1|%s" % (jid, amount, lock, self.sent())), self.ts(dsec))

    def sell(self, jid="1", why="손절"):
        self.e.on_message(line("SELL", "%s|005930|삼성|%s|%s" % (jid, why, self.sent())), self.ts(1))

    def go(self, n=1, step=4):
        for _ in range(n):
            self.e.tick()
            self.clock.go(step)

    def test_happy(self):
        self.rules(); self.buy(); self.go()
        self.assertEqual(self.kis.calls, [("order", "buy", 1000)])
        self.go(); self.assertTrue(self.e.st["jobs"]["1"]["buy"]["done"])
        self.sell(); self.go(2)
        self.assertIn(("order", "sell", 1000), self.kis.calls)
        self.assertEqual(len(self.slack.posts), 1)
        self.assertTrue(self.slack.posts[0].startswith("RESULT|pc1|1|005930|1000|1000|1000|"))

    def test_bad_sig_and_other_key(self):
        self.rules()
        self.e.on_message(line("BUY", "1|005930|x|1|1|v1|" + self.sent(), key="b" * 64), self.ts())
        self.e.on_message(line("BUY", "1|005930|x|1|1|v1|" + self.sent(), name="pc2"), self.ts())
        self.assertEqual(self.e.st["jobs"], {})

    def test_late_buy_dropped_but_late_sell_kept(self):
        self.rules(); self.buy(dsec=120)
        self.assertEqual(self.e.st["jobs"], {})
        self.buy(jid="2"); self.go(2)
        self.e.on_message(line("SELL", "2|005930|삼성|손절|20261124080000"), self.ts(5000))
        self.assertEqual(self.e.st["jobs"]["2"]["sell"]["pending"], "손절")

    def test_same_number_twice(self):
        self.rules(); self.buy(); self.buy(); self.go(3)
        self.assertEqual([c for c in self.kis.calls if c[0] == "order"], [("order", "buy", 1000)])

    def test_partial_then_retry(self):
        self.rules(); self.kis.fill["buy"] = [400]
        self.buy(); self.go()                      # 400 체결 · 600 열림
        self.go()                                  # 취소
        self.go()                                  # 남은 600 다시
        orders = [c for c in self.kis.calls if c[0] == "order"]
        self.assertEqual(orders, [("order", "buy", 1000), ("order", "buy", 600)])
        self.assertIn("cancel", [c[0] for c in self.kis.calls])

    def test_price_up_stop(self):
        self.rules(); self.kis.px = 1030; self.buy(); self.go()
        j = self.e.st["jobs"]["1"]
        self.assertTrue(j["buy"]["done"]); self.assertEqual(j["buy"]["filled"], 0)
        self.go()
        self.assertTrue(self.slack.posts[0].split("|")[6] == "0")       # 수량 0 · 못 삼 결과

    def test_time_stop_keeps_filled(self):
        self.rules(); self.kis.fill["buy"] = [300] + [0] * 500
        self.buy()
        self.go(n=120, step=4)                    # 8분 — 5분 넘음
        j = self.e.st["jobs"]["1"]
        self.assertTrue(j["buy"]["done"]); self.assertEqual(j["buy"]["filled"], 300)
        self.assertIn("분 지남", j["buy"]["why"])

    def test_sell_during_buy(self):
        self.rules(); self.kis.fill["buy"] = [200]
        self.buy(); self.go(); self.sell(); self.go(3)
        j = self.e.st["jobs"]["1"]
        self.assertEqual(j["buy"]["filled"], 200)
        self.assertIn(("order", "sell", 200), self.kis.calls)

    def test_zero_qty(self):
        self.rules(); self.buy(amount=500); self.go(2)
        self.assertEqual([c for c in self.kis.calls if c[0] == "order"], [])
        self.assertIn("0주", self.e.st["jobs"]["1"]["buy"]["why"])

    def test_no_rules_no_order(self):
        self.buy(); self.go(2)
        self.assertEqual(self.kis.calls, [])

    def test_limits(self):
        self.cfg["max_order_won"] = 300000
        self.e = self.mk(); self.rules(); self.buy(); self.go()
        self.assertEqual(self.kis.calls, [("order", "buy", 300)])

    def test_self_clean(self):
        self.rules(); self.buy(); self.go(2)
        self.clock.t = self.clock.t.replace(hour=15, minute=21)
        self.go(2)
        self.assertIn(("order", "sell", 1000), self.kis.calls)

    def test_crash_while_placing(self):
        self.rules(); self.buy()
        self.e.st["jobs"]["1"]["buy"]["placing"] = True; self.e.save()
        self.e = self.mk(); self.go(3)
        self.assertEqual(self.kis.calls, [])
        self.assertIn("확인 필요", self.e.st["jobs"]["1"]["buy"]["hold"])

    def test_restart_no_double_buy(self):
        self.rules(); self.buy(); self.go()
        self.e = self.mk(); self.buy(); self.go(3)
        self.assertEqual([c for c in self.kis.calls if c[0] == "order"], [("order", "buy", 1000)])

    def test_order_reject_retries_next(self):
        self.rules(); self.kis.fail_order = True; self.buy(); self.go()
        self.kis.fail_order = False; self.go(2)
        self.assertIn(("order", "buy", 1000), self.kis.calls)

    def test_sell_unknown_number(self):
        self.rules(); self.sell(jid="9"); self.go(2)
        self.assertEqual(self.kis.calls, [])

    def test_log_masks_and_filters(self):
        self.log.put("시험", "appkey=ABCDEFGH1234 token: XYZW99887766", jid="5", code="000660")
        rows = self.log.read(self.clock.t.strftime("%Y%m%d") if False else datetime.now(core.KST).strftime("%Y%m%d"), jid="5")
        self.assertTrue(rows and "ABCDEFGH" not in rows[-1]["text"] and "1234" in rows[-1]["text"])


if __name__ == "__main__":
    unittest.main()
