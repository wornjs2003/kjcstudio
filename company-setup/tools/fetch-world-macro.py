#!/usr/bin/env python3
"""세계지도 나라별 시황 — 아홉 곳의 주가 · 정책금리 · 물가 · 환율 · 10년 금리 · 경기선행 · 성장률 전망 · 다음 금리 회의를 받아
data/world-macro.json 에 둔다 (2026-10-12 · 재권님 시안 승인 「응 좋은거같아 해줘」 · flowmap.html 세계지도 말풍선이 읽는다).

  주가       나라 ETF 1개월(21봉 전 종가 대비 · 달러로 같은 잣대) — 이 폴더 서버(--port, 기본 8771)의 KIS 경로로 받는다
  정책금리   BIS WS_CBPOL(매일) · 한국은 한국은행 ECOS 722Y001 기준금리. 직전 결정 = 올해 마지막으로 바뀐 방향(안 바뀌었으면 동결)
  물가       OECD 소비자물가 전년비(월). 월 값이 없는 나라는 IMF 세계경제전망 지난해 연간 값 — 화면이 「연간」 을 붙인다
  환율       ECB 기준환율(유로 기준을 달러 기준으로 환산) · 1개월 변화. 미국은 FRED 달러지수
  10년 금리  미국 · 한국은 매일 값(FRED DGS10 · ECOS 국고채 10년), 나머지는 FRED 의 OECD 장기금리(달마다 · 늦게 나온다)
  경기선행   OECD 경기선행지수(100 = 장기 평균) · 전달 값과 함께
  성장률     IMF 세계경제전망 올해 실질성장률 전망
  다음 회의  미국만 — 연준 FOMC 일정 쪽에서 오늘 이후 첫 회의. 다른 나라는 아직 받는 곳이 없다(None → 화면 「—」)
  기간 흐름  series — 정책금리 · 물가 · 경기선행(2024-01 부터 달마다) · 달러지수 · 국채 금리(미국 3개월 · 2 · 10년 FRED · 한국 3 · 10년 ECOS 817Y002 · 1년 매일). 시황분석 탭(market.html) 그래프가 읽는다(2026-10-12 「응 좋아 붙여줘」).
             주가 · 금은 여기 두지 않는다 — 그 화면이 열 때 서버 /api/kis/chart 에서 받는다

받지 못한 것은 None 으로 두고 errors 에 이름만 적는다(주소에 키가 있어 문구를 안 남긴다). 키 없이 받는 곳이고 한국 금리만 ECOS 키를 쓴다.
IMF 는 파이썬 기본 요청을 403 으로 막아 curl 로 부른다(2026-10-12 실측).
"""
import csv, io, json, os, re, subprocess, sys
from datetime import datetime, timedelta, date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "..", "data", "world-macro.json")
from _secrets import secrets_path
SECRETS = secrets_path()   # KJC_SECRETS → ~/.kjc/secrets.json → holdings/secrets.json (tools/_secrets.py 한 곳)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _save import save   # --out · --also · 실패하면 옛 파일 그대로 — 넷이 함께 씀
PORT = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8771"
API = "http://localhost:%s/api" % PORT

# 열쇠: (이름, 나라 ETF, BIS 지역, OECD 지역, 통화, FRED 10년, IMF 지역, [경도, 위도] — 말풍선 자리(수도))
C = {
    "US": ("미국", "SPY", "US", "USA", "USD", "IRLTLT01USM156N", "USA", [-77.0, 38.9]),
    "EZ": ("유로존", "EZU", "XM", "EA20", "EUR", "IRLTLT01EZM156N", "EURO", [8.7, 50.1]),
    "JP": ("일본", "EWJ", "JP", "JPN", "JPY", "IRLTLT01JPM156N", "JPN", [139.7, 35.7]),
    "BR": ("브라질", "EWZ", "BR", "BRA", "BRL", None, "BRA", [-47.9, -15.8]),
    "CL": ("칠레", "ECH", "CL", "CHL", None, "IRLTLT01CLM156N", "CHL", [-70.6, -33.4]),
    "VN": ("베트남", "VNM", None, None, None, None, "VNM", [105.8, 21.0]),
    "AU": ("호주", "EWA", "AU", "AUS", "AUD", "IRLTLT01AUM156N", "AUS", [149.1, -35.3]),
    "KR": ("한국", "EWY", None, "KOR", "KRW", "IRLTLT01KRM156N", "KOR", [127.0, 37.5]),
    "CN": ("중국", "MCHI", "CN", "CHN", "CNY", None, "CHN", [116.4, 39.9]),
}
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}


def get(url, timeout=40):
    r = subprocess.run(["curl", "-sfL", "-m", str(timeout), url], capture_output=True)
    if r.returncode:
        raise RuntimeError("curl %d" % r.returncode)
    return r.stdout.decode("utf-8", "replace")


def rows(url):
    return list(csv.DictReader(io.StringIO(get(url))))


def fred(sid):
    l = [ln.split(",") for ln in get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid).strip().split("\n")[1:]]
    return [(a, float(b)) for a, b in l if b not in ("", ".")]


def rate_of(ser, src):
    """(날짜, 값) 과거 → 최근. 직전 결정 = 마지막으로 바뀐 방향 · since = 지금 값이 시작된 날."""
    last = ser[-1]
    prev = next((p for p in reversed(ser) if p[1] != last[1]), None)
    since = last[0]
    for d, v in reversed(ser):
        if v != last[1]:
            break
        since = d
    return {"v": last[1], "date": last[0], "dir": "hold" if prev is None else ("up" if last[1] > prev[1] else "down"),
            "since": since, "prev": prev and prev[1], "src": src}


SINCE = "2024-01-01"   # 기간 흐름의 처음 — 2024~2025 인하에서 2026 인상으로 돌아선 것이 보이는 자리


def monthly(ser):
    """(날짜, 값) 매일 → (YYYY-MM, 그달 마지막 값)."""
    m = {}
    for d, v in ser:
        m[d[:7]] = v
    return sorted(m.items())


def main():
    today = date.today()
    out = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "countries": {}, "series": {"rate": {}, "cpi": {}, "cli": {}, "dxy": [], "yld": {}}, "errors": {}}
    SER = out["series"]
    X = out["countries"]
    err = out["errors"]
    for k, v in C.items():
        X[k] = {"name": v[0], "at": v[7], "eq": None, "rate": None, "cpi": None, "fx": None, "dxy": None, "y10": None, "cli": None, "gdp": None, "meet": None}

    for k, v in C.items():                                   # 주가 — 나라 ETF 1개월
        try:
            j = json.loads(get("%s/kis/chart?code=%s&period=D" % (API, v[1])))
            c = [x for x in j["data"]["candles"] if x.get("close")]
            X[k]["eq"] = {"etf": v[1], "m1": round((c[-1]["close"] / c[-22]["close"] - 1) * 100, 1), "date": c[-1]["ts"], "src": "KIS 해외 일봉"}
        except Exception as ex:
            err["eq-" + k] = type(ex).__name__

    try:                                                      # 정책금리 — BIS
        areas = "+".join(v[2] for v in C.values() if v[2])
        s = {}
        for x in rows("https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.%s?startPeriod=%s&format=csv" % (areas, SINCE)):
            if x["OBS_VALUE"] and x["OBS_VALUE"].lower() != "nan":
                s.setdefault(x["REF_AREA"], []).append((x["TIME_PERIOD"], float(x["OBS_VALUE"])))
        for k, v in C.items():
            if v[2] in s:
                ser = sorted(s[v[2]])
                X[k]["rate"] = rate_of([p for p in ser if p[0] >= "%d-01-01" % today.year] or ser[-1:], "BIS 중앙은행 정책금리")
                SER["rate"][k] = monthly(ser)
    except Exception as ex:
        err["bis"] = type(ex).__name__
    try:                                                      # 한국 기준금리 — ECOS
        key = json.load(open(SECRETS, encoding="utf-8"))["ecos"]["api_key"]
        rr = json.loads(get("https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/2000/722Y001/D/%s/%s/0101000"
                            % (key, SINCE.replace("-", ""), today.strftime("%Y%m%d"))))["StatisticSearch"]["row"]
        ser = [("%s-%s-%s" % (x["TIME"][:4], x["TIME"][4:6], x["TIME"][6:]), float(x["DATA_VALUE"])) for x in rr]
        X["KR"]["rate"] = rate_of([p for p in ser if p[0] >= "%d-01-01" % today.year] or ser[-1:], "한국은행 ECOS 기준금리")
        SER["rate"]["KR"] = monthly(ser)
    except Exception as ex:
        err["ecos"] = type(ex).__name__

    try:                                                      # 물가 — OECD 월
        start = SINCE[:7]
        recent = (today.replace(day=1) - timedelta(days=200)).strftime("%Y-%m")
        o, hist = {}, {}
        for x in rows("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/.M.N.CPI.PA._T.N.GY?startPeriod=%s"
                      "&dimensionAtObservation=AllDimensions&format=csvfilewithlabels" % start):
            if x["OBS_VALUE"]:
                if x["TIME_PERIOD"] >= recent:   # 말풍선 값은 반년 안 것만 — 더 낡으면 IMF 지난해 연간 값으로(유로존은 2025-12 에서 멈춰 있다)
                    o[x["REF_AREA"]] = max(o.get(x["REF_AREA"], ("", "")), (x["TIME_PERIOD"], x["OBS_VALUE"]))
                hist.setdefault(x["REF_AREA"], []).append((x["TIME_PERIOD"], round(float(x["OBS_VALUE"]), 2)))
        for k, v in C.items():
            if v[3] in hist:
                SER["cpi"][k] = sorted(hist[v[3]])
            if v[3] in o:
                X[k]["cpi"] = {"v": round(float(o[v[3]][1]), 1), "date": o[v[3]][0], "annual": False, "src": "OECD 소비자물가 전년비(월)"}
    except Exception as ex:
        err["oecd-cpi"] = type(ex).__name__
    try:                                                      # 월 값이 없는 나라 — IMF 지난해 연간
        y = str(today.year - 1)
        miss = [k for k in C if not X[k]["cpi"]]
        if miss:
            im = json.loads(get("https://www.imf.org/external/datamapper/api/v1/PCPIPCH/%s?periods=%s" % ("/".join(C[k][6] for k in miss), y)))["values"]["PCPIPCH"]
            for k in miss:
                if C[k][6] in im and y in im[C[k][6]]:
                    X[k]["cpi"] = {"v": round(im[C[k][6]][y], 1), "date": y, "annual": True, "src": "IMF 세계경제전망 물가(연)"}
    except Exception as ex:
        err["imf-cpi"] = type(ex).__name__

    try:                                                      # 환율 — ECB 유로 기준을 달러 기준으로
        curs = sorted({v[4] for v in C.values() if v[4] and v[4] != "EUR"} | {"USD"})
        fx = {}
        for x in rows("https://data-api.ecb.europa.eu/service/data/EXR/D.%s.EUR.SP00.A?startPeriod=%s&format=csvdata"
                      % ("+".join(curs), (today - timedelta(days=60)).isoformat())):
            if x["OBS_VALUE"]:
                fx.setdefault(x["CURRENCY"], {})[x["TIME_PERIOD"]] = float(x["OBS_VALUE"])
        days = sorted(fx["USD"])
        d1, d0 = days[-1], days[-22]
        for k, v in C.items():
            cur = v[4]
            if cur == "EUR":
                X[k]["fx"] = {"pair": "달러/유로", "v": round(fx["USD"][d1], 4), "m1": round((fx["USD"][d1] / fx["USD"][d0] - 1) * 100, 1), "date": d1, "src": "ECB 기준환율"}
            elif cur and cur != "USD" and cur in fx:
                a, b = fx[cur][d1] / fx["USD"][d1], fx[cur][d0] / fx["USD"][d0]
                X[k]["fx"] = {"pair": cur + "/달러", "v": round(a, 2), "m1": round((a / b - 1) * 100, 1), "date": d1, "src": "ECB 기준환율(달러 기준 환산)"}
    except Exception as ex:
        err["ecb-fx"] = type(ex).__name__
    try:                                                      # 미국 — 달러지수
        l = fred("DTWEXBGS")
        X["US"]["dxy"] = {"v": round(l[-1][1], 1), "m1": round((l[-1][1] / l[-22][1] - 1) * 100, 1), "date": l[-1][0], "src": "FRED 달러지수(교역가중)"}
        SER["dxy"] = [(d, v) for d, v in l if d >= (today - timedelta(days=380)).isoformat()]
    except Exception as ex:
        err["dxy"] = type(ex).__name__

    y1 = (today - timedelta(days=380)).isoformat()             # 국채 금리 1년 매일 — 시황분석 탭 채권 그래프 (2026-10-12 재권님 「시황에 채권도」)
    for name, sid in (("US3M", "DGS3MO"), ("US2", "DGS2"), ("US10", "DGS10")):   # 3개월 — 10년 − 3개월 금리차로 침체 확률(뉴욕 연준 · 에스트레야 · 미시킨)
        try:
            SER["yld"][name] = [(d, v) for d, v in fred(sid) if d >= y1]
        except Exception as ex:
            err["yld-" + name] = type(ex).__name__
    try:
        key = json.load(open(SECRETS, encoding="utf-8"))["ecos"]["api_key"]
        for name, item in (("KR3", "010200000"), ("KR10", "010210000")):
            rr = json.loads(get("https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/400/817Y002/D/%s/%s/%s"
                                % (key, y1.replace("-", ""), today.strftime("%Y%m%d"), item)))["StatisticSearch"]["row"]
            SER["yld"][name] = [("%s-%s-%s" % (x["TIME"][:4], x["TIME"][4:6], x["TIME"][6:]), float(x["DATA_VALUE"])) for x in rr]
    except Exception as ex:
        err["yld-KR"] = type(ex).__name__

    for k, v in C.items():                                   # 10년 금리 — FRED 월
        if v[5]:
            try:
                l = fred(v[5])
                X[k]["y10"] = {"v": round(l[-1][1], 2), "date": l[-1][0][:7], "src": "FRED · OECD 장기금리(월)"}
            except Exception as ex:
                err["y10-" + k] = type(ex).__name__

    for k, n, src in (("US", "US10", "FRED DGS10 · 미국 국채 10년(매일)"), ("KR", "KR10", "한국은행 ECOS 817Y002 · 국고채 10년(매일)")):
        ser = SER["yld"].get(n)                               # 매일 값이 있는 나라는 말풍선도 매일 값 (2026-10-12 재권님 「매일값이 있어야」) — 달마다 값은 넉 달 늦었다
        if ser:
            X[k]["y10"] = {"v": round(ser[-1][1], 2), "date": ser[-1][0], "daily": True, "src": src}

    try:                                                      # 경기선행 — OECD
        cl = {}
        for x in rows("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/.M.LI...AA...H?startPeriod=%s"
                      "&dimensionAtObservation=AllDimensions&format=csvfilewithlabels" % SINCE[:7]):
            if x["OBS_VALUE"]:
                cl.setdefault(x["REF_AREA"], []).append((x["TIME_PERIOD"], float(x["OBS_VALUE"])))
        for k, v in C.items():
            if v[3] in cl and len(cl[v[3]]) >= 2:
                ser = sorted(cl[v[3]])
                SER["cli"][k] = [(d, round(x, 2)) for d, x in ser]
                X[k]["cli"] = {"v": round(ser[-1][1], 1), "prev": round(ser[-2][1], 1), "date": ser[-1][0], "src": "OECD 경기선행지수(100 = 장기 평균)"}
    except Exception as ex:
        err["oecd-cli"] = type(ex).__name__

    try:                                                      # 성장률 전망 — IMF
        y = str(today.year)
        g = json.loads(get("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/%s?periods=%s" % ("/".join(v[6] for v in C.values()), y)))["values"]["NGDP_RPCH"]
        for k, v in C.items():
            if v[6] in g and y in g[v[6]]:
                X[k]["gdp"] = {"v": round(g[v[6]][y], 1), "date": y + " 전망", "src": "IMF 세계경제전망 실질성장률"}
    except Exception as ex:
        err["imf-gdp"] = type(ex).__name__

    try:                                                      # 다음 금리 회의 — 미국 FOMC
        s = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
        for yr in (today.year, today.year + 1):
            i = s.find("%d FOMC Meetings" % yr)
            if i < 0:
                continue
            t = s[i:]
            j = t.find("FOMC Meetings", 30)
            t = t[:j] if j > 0 else t
            hit = None
            for mon, dd in re.findall(r'fomc-meeting__month[^>]*>(?:<strong>)?([^<]+)<.*?fomc-meeting__date[^>]*>([^<]+)<', t, re.S):
                m = MONTHS.get(mon.strip().split("/")[-1])
                nums = re.findall(r"\d+", dd)
                if m and nums and date(yr, m, int(nums[-1])) >= today:
                    hit = {"v": "%d월 %s일" % (m, "~".join(nums)), "date": "%d-%02d-%02d" % (yr, m, int(nums[0])), "name": "FOMC", "src": "연준 FOMC 일정"}
                    break
            if hit:
                X["US"]["meet"] = hit
                break
    except Exception as ex:
        err["fomc"] = type(ex).__name__

    _, bad = save(out, OUT, list(err), indent=1)
    filled = sum(1 for c in X.values() for f in ("eq", "rate", "cpi", "y10", "cli", "gdp") if c[f])
    print("✓ 받음 — 나라 %d · 채운 칸 %d / %d · 못 받음 %d" % (len(X), filled, len(X) * 6, len(err)))
    for k, v in err.items():
        print("  ✗", k, v)
    return bad


if __name__ == "__main__":
    sys.exit(main())
