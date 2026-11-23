# -*- coding: utf-8 -*-
"""한국투자증권 연결 — 주문 컴퓨터가 쓰는 증권사 한 갈래 (2026-11-23 · 개발2).

증권사 연결만 갈아 끼우는 꼴 — 재권님 「여러증권사로 하고싶은데」 → 「응 그렇게 해」. 다른 증권사는 같은 네 함수
(price · order_market · order_status · cancel)를 가진 파일을 더하면 된다.

경로 · TR · 칸 이름은 한국투자 공식 예제(github koreainvestment/open-trading-api · examples_llm · strategy_builder)에서 확인한 것만 —
    현재가       GET  /uapi/domestic-stock/v1/quotations/inquire-price      FHKST01010100 · 응답 output.stck_prpr
    주문         POST /uapi/domestic-stock/v1/trading/order-cash        매수 TTTC0012U · 매도 TTTC0011U(모의 VTTC…) · ORD_DVSN 01 = 시장가 · ORD_UNPR 0 ·
                                                                       EXCG_ID_DVSN_CD KRX · SLL_TYPE 01(일반매도) · 응답 output.ODNO · KRX_FWDG_ORD_ORGNO
    정정취소     POST /uapi/domestic-stock/v1/trading/order-rvsecncl    TTTC0013U(모의 VTTC0013U) · RVSE_CNCL_DVSN_CD 02 = 취소 · QTY_ALL_ORD_YN Y
    체결 조회    GET  /uapi/domestic-stock/v1/trading/inquire-daily-ccld TTTC0081R(모의 VTTC0081R · 3개월 안) · output1 odno · ord_qty · tot_ccld_qty · avg_prvs · rmn_qty · cncl_yn
    토큰         POST /oauth2/tokenP — 앱키마다 자주 못 받아 파일에 남겨 다시 쓴다(크로스체크 ⑤)
확인 못 한 것 — 정정취소 응답 칸 · 체결 조회에서 「열린 주문」 을 무엇으로 가르는지(여기서는 잔여수량 rmn_qty > 0 · 취소 아님) — 모의투자에서 처음 잴 것.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HOSTS = {"real": "https://openapi.koreainvestment.com:9443", "demo": "https://openapivts.koreainvestment.com:29443"}
TR = {"real": {"buy": "TTTC0012U", "sell": "TTTC0011U", "cancel": "TTTC0013U", "ccld": "TTTC0081R"},
      "demo": {"buy": "VTTC0012U", "sell": "VTTC0011U", "cancel": "VTTC0013U", "ccld": "VTTC0081R"}}
MIN_GAP = 0.25            # 부르기 사이 최소 간격(초) — 앱키마다 초당 한도 안(모의는 더 낮다고 알려짐 · 숫자 확인 못 함 → 넉넉히)


class KisError(Exception):
    pass


class KisUnsure(Exception):
    """증권사가 받았는지 모르는 실패 — 응답 시간 초과 · 연결 끊김 · HTTP 오류. 주문에서는 실패로 보지 않고 「확인 필요」 로 멈춘다(qa 11-23 ②).
    KisError 는 증권사가 rt_cd 로 거절했다고 답한 것 — 그때만 다음 바퀴에 다시 넣는다."""


class Kis:
    def __init__(self, c, token_path):
        self.env = c["env"]                       # demo | real — real 은 재권님 「켜기」 지시 뒤에만
        if self.env not in HOSTS:
            raise KisError("env 는 demo 또는 real")
        self.host = HOSTS[self.env]
        self.appkey, self.secret = c["app_key"], c["app_secret"]
        self.cano, self.prod = c["account8"], c.get("account2") or "01"
        self.token_path = token_path
        self._last = 0.0

    def _wait(self):
        d = time.time() - self._last
        if d < MIN_GAP:
            time.sleep(MIN_GAP - d)
        self._last = time.time()

    def _token(self):
        try:
            with open(self.token_path, encoding="utf-8") as f:
                t = json.load(f)
            if t.get("exp", 0) - 600 > time.time() and t.get("env") == self.env:
                return t["token"]
        except (OSError, ValueError):
            pass
        body = json.dumps({"grant_type": "client_credentials", "appkey": self.appkey, "appsecret": self.secret}).encode()
        req = urllib.request.Request(self.host + "/oauth2/tokenP", data=body, headers={"content-type": "application/json"})
        self._wait()
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        tok = j.get("access_token")
        if not tok:
            raise KisError("토큰 못 받음 — %s" % str(j.get("error_description") or j)[:80])
        with open(self.token_path, "w", encoding="utf-8") as f:
            json.dump({"token": tok, "exp": time.time() + int(j.get("expires_in", 3600)), "env": self.env}, f)
        os.chmod(self.token_path, 0o600)
        return tok

    def _call(self, method, path, tr_id, params=None, body=None):
        h = {"content-type": "application/json; charset=utf-8", "authorization": "Bearer " + self._token(),
             "appkey": self.appkey, "appsecret": self.secret, "tr_id": tr_id, "custtype": "P"}
        url = self.host + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        self._wait()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=15) as r:
                j = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise KisUnsure("HTTP %s" % e.code)          # 받았는지 모름 — 주문이면 두 번 안 넣게 멈춤(qa 11-23 ②)
        if str(j.get("rt_cd")) != "0":
            raise KisError("%s %s" % (j.get("msg_cd"), j.get("msg1")))
        return j

    def price(self, code):
        try:
            j = self._call("GET", "/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
                           {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
            return float(j["output"]["stck_prpr"])
        except (KisError, KisUnsure, KeyError, ValueError, OSError):   # 현재가 5xx · 시간 초과 한 번에 그 바퀴 전체가 끊기지 않게(개념정의 덧 ①)
            return None

    def order_market(self, code, qty, side):
        b = {"CANO": self.cano, "ACNT_PRDT_CD": self.prod, "PDNO": code, "ORD_DVSN": "01", "ORD_QTY": str(int(qty)), "ORD_UNPR": "0",
             "EXCG_ID_DVSN_CD": "KRX"}
        if side == "sell":
            b["SLL_TYPE"] = "01"
        j = self._call("POST", "/uapi/domestic-stock/v1/trading/order-cash", TR[self.env][side], body=b)
        o = j.get("output") or {}
        if not o.get("ODNO"):
            raise KisError("주문번호 없음")
        return {"odno": o["ODNO"], "orgno": o.get("KRX_FWDG_ORD_ORGNO")}

    def cancel(self, odno, orgno, code):
        b = {"CANO": self.cano, "ACNT_PRDT_CD": self.prod, "KRX_FWDG_ORD_ORGNO": orgno or "", "ORGN_ODNO": odno, "ORD_DVSN": "01",
             "RVSE_CNCL_DVSN_CD": "02", "ORD_QTY": "0", "ORD_UNPR": "0", "QTY_ALL_ORD_YN": "Y", "EXCG_ID_DVSN_CD": "KRX"}
        self._call("POST", "/uapi/domestic-stock/v1/trading/order-rvsecncl", TR[self.env]["cancel"], body=b)

    def order_status(self, odno, code):
        """그 주문의 체결 — {filled, avg, open} | None(못 찾음)."""
        d = time.strftime("%Y%m%d")
        j = self._call("GET", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", TR[self.env]["ccld"],
                       {"CANO": self.cano, "ACNT_PRDT_CD": self.prod, "INQR_STRT_DT": d, "INQR_END_DT": d, "SLL_BUY_DVSN_CD": "00",
                        "PDNO": code, "CCLD_DVSN": "00", "INQR_DVSN": "00", "INQR_DVSN_3": "00", "ORD_GNO_BRNO": "", "ODNO": odno,
                        "INQR_DVSN_1": "", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""})
        for r in j.get("output1") or []:
            if str(r.get("odno", "")).lstrip("0") == str(odno).lstrip("0"):
                filled = int(float(r.get("tot_ccld_qty") or 0))
                rmn = int(float(r.get("rmn_qty") or 0))
                return {"filled": filled, "avg": float(r.get("avg_prvs") or 0) or None, "open": rmn > 0 and r.get("cncl_yn") != "Y"}
        return None
