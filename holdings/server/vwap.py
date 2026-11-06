"""VWAP(거래량 가중 평균가) — 분봉에 그날 정규장 누적 값을 붙인다 (2026-11-06)

재권님 — 홈 훑기 12 「단기매매 정보 더하기」 → 「VWAP 가 뭐지?」 → 「응 만들어 설명도 넣어주고」(정규장 09:00 부터 · 검은 점선).
셈은 이 한 곳이다 — 화면(chart.js)은 봉에 붙은 `vwap` 을 선으로 그리기만 한다.

    vwap = Σ(대표가 × 거래량) ÷ Σ거래량      대표가 = (고가 + 저가 + 종가) ÷ 3
    하루마다 0 부터 · 정규장(SESSION) 안 봉만 더한다 · 밖 봉과 거래량 0 이 이어진 앞쪽은 None
"""

SESSION = ("0900", "1530")      # 정규장 — 봉 시각(ts 의 HHMM · 봉이 시작하는 시각)이 이 안이면 더한다


def attach(rows):
    """분봉 목록(ts 오름차순)의 각 봉에 `vwap` 을 붙인다. 정규장 밖 봉은 None. 목록을 그대로 돌려준다."""
    day, pv, vol = None, 0.0, 0
    for r in rows:
        ts = str(r.get("ts", ""))
        d, hm = ts[:8], ts[8:12]
        if d != day:
            day, pv, vol = d, 0.0, 0
        if len(hm) == 4 and SESSION[0] <= hm < SESSION[1]:
            v = r.get("volume") or 0
            hi, lo, cl = r.get("high"), r.get("low"), r.get("close")
            if v > 0 and hi and lo and cl:
                pv += (hi + lo + cl) / 3.0 * v
                vol += v
            r["vwap"] = round(pv / vol, 2) if vol else None
        else:
            r["vwap"] = None
    return rows
