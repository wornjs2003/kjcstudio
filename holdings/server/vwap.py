"""VWAP(거래량 가중 평균가) — 분봉에 장마다 누적 값을 붙인다 (2026-11-06 · 11-07 토스처럼 장마다 새로)

재권님 — 홈 훑기 12 「단기매매 정보 더하기」 → 「VWAP 가 뭐지?」 → 「응 만들어 설명도 넣어주고」(검은 점선).
셈은 이 한 곳이다 — 화면(chart.js)은 봉에 붙은 `vwap` 을 선으로 그리기만 한다.

장마다 0 부터 다시 센다 (2026-11-07 재권님 「vwap 값 … 토스증권에서 보는값이랑 많이 다른거같아」 → 「토스랑 비교하고 봐봐」 →
「토스꺼 분석해서 똑같이 해줘」). 토스 그림(삼성 11-06 5분봉)을 눈금으로 읽어 맞춘 값 — 우리 봉으로 장마다 새로 셈한 것과
장 전 08:45 179,480 ↔ 179,539 · 정규장 11:50 188,440 ↔ 188,464 · 15:10 189,400 ↔ 189,382 · 장 후 20:00 191,700 ↔ 191,788.
(정규장 두 값은 토스 그림에 09:00~09:25 봉이 없어 09:30 부터 셈한 것이다 — 우리는 09:00 부터 센다.)
처음 판(정규장 09:00~15:30 만)은 장 전 · 장 후 선이 없었고, 하루 통째로 셈한 판(11-07 잠깐)은 토스보다 2,000~4,000원 낮았다.

    vwap = Σ(대표가 × 거래량) ÷ Σ거래량      대표가 = (고가 + 저가 + 종가) ÷ 3
    장(SESSIONS)마다 0 부터 · 장 밖 봉과 거래량 0 이 이어진 앞쪽은 None
    바로 앞 봉과 시 · 고 · 저 · 종 · 거래량이 다 같은 봉은 더하지 않는다 — KIS 가 빈 칸을 앞 봉 그대로 채워 주어
    거래량이 두 번 들어갔다(11-06 삼성 09:05~09:25 다섯 칸 · 15:25 = 15:20)
"""

# 장 — (이름, 첫 봉 시각, 이 시각 앞까지) · 봉 시각은 ts 의 HHMM(봉이 시작하는 시각)
SESSIONS = (
    ("장 전", "0800", "0850"),    # 넥스트레이드 프리마켓
    ("정규장", "0900", "1530"),   # KRX 정규장(통합 봉)
    ("장 후", "1540", "2005"),    # 넥스트레이드 애프터마켓 · 마지막 20:00 봉까지
)


def _session(hm):
    for name, a, b in SESSIONS:
        if a <= hm < b:
            return name
    return None


def attach(rows):
    """분봉 목록(ts 오름차순)의 각 봉에 `vwap` 을 붙인다. 장 밖 봉은 None. 목록을 그대로 돌려준다."""
    key, pv, vol, prev = None, 0.0, 0, None
    for r in rows:
        ts = str(r.get("ts", ""))
        d, hm = ts[:8], ts[8:12]
        ses = _session(hm) if len(hm) == 4 else None
        if ses is None:
            r["vwap"] = None
            continue
        if (d, ses) != key:
            key, pv, vol = (d, ses), 0.0, 0
        v = r.get("volume") or 0
        hi, lo, cl = r.get("high"), r.get("low"), r.get("close")
        sig = (r.get("open"), hi, lo, cl, v)
        dup, prev = sig == prev, sig
        if v > 0 and hi and lo and cl and not dup:
            pv += (hi + lo + cl) / 3.0 * v
            vol += v
        r["vwap"] = round(pv / vol, 2) if vol else None
    return rows
