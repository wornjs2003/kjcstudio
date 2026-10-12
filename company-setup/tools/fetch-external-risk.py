#!/usr/bin/env python3
"""대외변수 — 전쟁 · 정치 · 무역 같은 외부 요인을 숫자로 센 지수를 받아 data/external-risk.json 에 둔다
(2026-10-12 재권님 「대외변수에 들어갈만한것들 찾아보라」 → 조사 → 「응 해줘」). 시황분석 탭 「대외변수」 층(js/market-ext.js)이 읽는다. 손으로 돌린다.

  지정학 위험(GPR)    Caldara · Iacoviello(2022) — 전쟁 · 테러 · 군사 긴장 기사 비율. 매일(세계) · 달마다(나라별 · 한국 칸은 기사 중 비율 %)
                      matteoiacoviello.com/gpr_files/*.dta (Stata 118 — 이 기계에 엑셀 읽는 부품이 없어 Stata 파일을 직접 읽는다)
                      100 = 1985~2019 평균. 파일의 event 칸(큰 사건 날)도 함께 둔다
  정책 불확실성(EPU)  Baker · Bloom · Davis — 미국 신문 매일. policyuncertainty.com All_Daily_Policy_Data.csv · 100 = 1985~2009 평균
                      한국 판은 2021-01 에서 멈춰 있어 안 쓴다(2026-10-12 실측)
  무역정책 불확실성    Caldara 외 — 매일. matteoiacoviello.com/tpu_files/tpu_web_latest.xlsx 의 TPU_DAILY
  공포 지수           VIX(미국 주가 옵션 · FRED VIXCLS) · OVX(원유 옵션 · FRED OVXCLS) — FRED 열쇠 holdings/secrets.json fred

받지 못한 것은 빈 값으로 두고 errors 에 이름만 적는다(주소에 열쇠가 있는 것도 있어 문구를 안 남긴다).
"""
import csv, io, json, os, re, struct, subprocess, sys, urllib.parse, zipfile
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "..", "data", "external-risk.json")
SECRETS = os.path.join(ROOT, "holdings", "secrets.json")
GPR = "https://www.matteoiacoviello.com/gpr_files/"
SINCE = (date.today() - timedelta(days=372)).isoformat()


def raw(url, timeout=60):
    r = subprocess.run(["curl", "-sfL", "-m", str(timeout), "-A", "Mozilla/5.0", url], capture_output=True)
    if r.returncode:
        raise RuntimeError("curl %d" % r.returncode)
    return r.stdout


def read_dta(b, want):
    """Stata 118(little-endian)에서 want 칸만 — 숫자 · 고정 길이 글자."""
    if b"<release>118</release>" not in b[:80] or b"<byteorder>LSF" not in b[:80]:
        raise ValueError("Stata 118 LSF 아님")
    K = struct.unpack_from("<H", b, b.index(b"<K>") + 3)[0]
    N = struct.unpack_from("<Q", b, b.index(b"<N>") + 3)[0]
    off = struct.unpack_from("<14Q", b, b.index(b"<map>") + 5)
    types = struct.unpack_from("<%dH" % K, b, off[2] + len(b"<variable_types>"))
    v = off[3] + len(b"<varnames>")
    names = [b[v + 129 * j:v + 129 * (j + 1)].split(b"\0")[0].decode() for j in range(K)]
    size = {65526: 8, 65527: 4, 65528: 4, 65529: 2, 65530: 1, 32768: 8}
    fmt = {65526: "<d", 65527: "<f", 65528: "<i", 65529: "<h", 65530: "<b"}
    w = [size.get(t, t) for t in types]
    pos = [sum(w[:j]) for j in range(K)]
    rw, d = sum(w), off[9] + len(b"<data>")
    out = {n: [] for n in names if n in want}
    for r in range(N):
        base = d + r * rw
        for j, n in enumerate(names):
            if n not in out:
                continue
            t = types[j]
            if t in fmt:
                x = struct.unpack_from(fmt[t], b, base + pos[j])[0]
                out[n].append(None if (t == 65526 and x > 8.9e307) or (t == 65527 and x > 1.7e38) else x)
            elif t <= 2045:
                out[n].append(b[base + pos[j]:base + pos[j] + t].split(b"\0")[0].decode("utf-8", "replace").strip())
            else:
                out[n].append(None)
    return out


def r2(x):
    return None if x is None else round(x, 2)


def main():
    err, X = {}, {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "since": SINCE}
    try:   # 지정학 위험 — 매일(세계)
        o = read_dta(raw(GPR + "data_gpr_daily_recent.dta"), {"DAY", "GPRD", "GPRD_MA30", "event"})
        days = ["%s-%s-%s" % (d[:4], d[4:6], d[6:]) for d in o["DAY"]]
        X["gpr"] = [[d, r2(v), r2(m)] for d, v, m in zip(days, o["GPRD"], o["GPRD_MA30"]) if d >= SINCE and v is not None]
        X["gprEvents"] = [[d, e] for d, e in zip(days, o["event"]) if e]
    except Exception as ex:
        X["gpr"], X["gprEvents"], err["gpr"] = [], [], type(ex).__name__
    try:   # 지정학 위험 — 달마다(세계 · 한국)
        o = read_dta(raw(GPR + "data_gpr_export.dta"), {"month", "GPR", "GPRC_KOR"})
        ym = lambda m: "%04d-%02d" % (1960 + int(m) // 12, int(m) % 12 + 1)   # Stata 달 = 1960-01 부터 센 달 수
        X["gprMonthly"] = [[ym(m), r2(g), r2(k)] for m, g, k in zip(o["month"], o["GPR"], o["GPRC_KOR"]) if m is not None and ym(m) >= "2020-01"]
    except Exception as ex:
        X["gprMonthly"], err["gprMonthly"] = [], type(ex).__name__
    try:   # 정책 불확실성 — 미국 매일 · 30일 평균을 여기서 만든다(파일에 없다)
        rows = list(csv.reader(io.StringIO(raw("https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv").decode("utf-8", "replace"))))[1:]
        ser = [("%s-%02d-%02d" % (r[2], int(r[1]), int(r[0])), float(r[3])) for r in rows if len(r) >= 4 and r[3]]
        X["epu"] = [[d, r2(v), r2(sum(x for _, x in ser[max(0, i - 29):i + 1]) / len(ser[max(0, i - 29):i + 1]))] for i, (d, v) in enumerate(ser) if d >= SINCE]
    except Exception as ex:
        X["epu"], err["epu"] = [], type(ex).__name__
    try:   # 무역정책 불확실성 — 매일
        z = zipfile.ZipFile(io.BytesIO(raw("https://www.matteoiacoviello.com/tpu_files/tpu_web_latest.xlsx")))
        names = re.findall(r'<sheet [^>]*name="([^"]+)"', z.read("xl/workbook.xml").decode())
        sh = z.read("xl/worksheets/sheet%d.xml" % (names.index("TPU_DAILY") + 1)).decode()
        out = []
        for row in re.findall(r"<row [^>]*>(.*?)</row>", sh)[1:]:
            c = dict(re.findall(r'<c r="([A-Z]+)\d+"[^>]*><v>([^<]*)</v>', row))
            if "A" in c and "D" in c:
                d = (date(1899, 12, 30) + timedelta(days=int(float(c["A"])))).isoformat()   # 엑셀 날짜 수
                if d >= SINCE:
                    out.append([d, r2(float(c["D"])), r2(float(c["F"])) if "F" in c else None])
        X["tpu"] = out
    except Exception as ex:
        X["tpu"], err["tpu"] = [], type(ex).__name__
    try:   # 공포 지수
        k = json.load(open(SECRETS, encoding="utf-8"))["fred"]["api_key"]
        for key, sid in (("vix", "VIXCLS"), ("ovx", "OVXCLS")):
            u = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(dict(series_id=sid, api_key=k, file_type="json", observation_start=SINCE))
            X[key] = [[o["date"], float(o["value"])] for o in json.loads(raw(u))["observations"] if o["value"] != "."]
    except Exception as ex:
        X.setdefault("vix", []), X.setdefault("ovx", [])
        err["fred"] = type(ex).__name__
    X["errors"] = err
    X["src"] = "지정학 위험 Caldara · Iacoviello(matteoiacoviello.com · 100 = 1985~2019 평균) · 정책 불확실성 Baker · Bloom · Davis(policyuncertainty.com · 100 = 1985~2009 평균) · 무역정책 불확실성 Caldara 외 · VIX · OVX FRED"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(X, f, ensure_ascii=False, separators=(",", ":"))
    last = lambda s: s[-1] if s else "—"
    print("지정학 %s · 한국 달 %s · 정책 %s · 무역 %s · VIX %s · OVX %s · 큰 사건 %d · 못 받은 것 %s" % (
        last(X["gpr"]), last(X["gprMonthly"]), last(X["epu"]), last(X["tpu"]), last(X["vix"]), last(X["ovx"]), len(X["gprEvents"]), ", ".join(err) or "없음"))
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
