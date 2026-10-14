#!/usr/bin/env python3
"""대외변수 — 전쟁 · 정치 · 무역 같은 외부 요인을 숫자로 센 지수를 받아 data/external-risk.json 에 둔다
(2026-10-12 재권님 「대외변수에 들어갈만한것들 찾아보라」 → 조사 → 「응 해줘」). 시황분석 탭 「대외변수」 층(js/market-ext.js)이 읽는다.
매일 아침 launchd(launchd/kr.kjcstudio.market-data.plist)가 --out <이름>-live.json 으로 돌린다 · 손으로 돌리면 씨앗 파일에 쓴다.

  지정학 위험(GPR)    Caldara · Iacoviello(2022) — 전쟁 · 테러 · 군사 긴장 기사 비율. 매일(세계) · 달마다(나라별 · 한국 칸은 기사 중 비율 %)
                      matteoiacoviello.com/gpr_files/*.dta (Stata 118 — 이 기계에 엑셀 읽는 부품이 없어 Stata 파일을 직접 읽는다)
                      100 = 1985~2019 평균. 파일의 event 칸(큰 사건 날)도 함께 둔다
  정책 불확실성(EPU)  Baker · Bloom · Davis — 미국 신문 매일. policyuncertainty.com All_Daily_Policy_Data.csv · 100 = 1985~2009 평균
                      한국 판은 2021-01 에서 멈춰 있어 안 쓴다(2026-10-12 실측)
  무역정책 불확실성    Caldara 외 — 매일. matteoiacoviello.com/tpu_files/tpu_web_latest.xlsx 의 TPU_DAILY
  공포 지수           VIX(미국 주가 옵션 · FRED VIXCLS) · OVX(원유 옵션 · FRED OVXCLS) — FRED 열쇠는 열쇠 파일(tools/_secrets.py 순서)의 fred

튄 날(spikes) — 지수마다 「그날 값 ÷ 앞 20개 값 평균」 이 받은 기간(1년) 안에서 위 5% 이상인 날. 아래 spikes() 참고.

받지 못한 것은 빈 값으로 두고 errors 에 이름만 적는다(주소에 열쇠가 있는 것도 있어 문구를 안 남긴다).
"""
import csv, io, json, math, os, re, struct, subprocess, sys, urllib.parse, zipfile
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "..", "data", "external-risk.json")
from _secrets import secrets_path
SECRETS = secrets_path()   # KJC_SECRETS → ~/.kjc/secrets.json → holdings/secrets.json (tools/_secrets.py 한 곳)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _save import save   # --out · --also · 실패하면 옛 파일 그대로 — 넷이 함께 씀
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


SPIKE_PREV = 20      # 견줄 앞 값 개수 — 「최근에 얼마나 올랐나」 의 「최근」
SPIKE_TOP = 0.05     # 위 몇 % 를 튄 날로 보나 (2026-10-14 재권님 「가」 — 지수마다 지난 1년 위 5%)
SPIKE_NAMES = {"gpr": "지정학 위험", "epu": "정책 불확실성(미국)", "tpu": "무역정책 불확실성", "vix": "VIX", "ovx": "OVX"}


def spikes(X):
    """튄 날 — 지수마다 그날 값 ÷ 앞 SPIKE_PREV 개 값 평균을 내고, 받은 기간 안에서 그 비율의 위 SPIKE_TOP 이상인 날을 고른다.
    경계 숫자는 박지 않고 받을 때마다 다시 센다 — 기사 지수(GPR · EPU · TPU)는 출렁임이 커 1.7~1.8배가 위 5% 이고
    VIX 는 1.24배 언저리라 한 잣대로 못 잰다(2026-10-13 실측). 오른 쪽만 센다 — 위험 지수가 내린 날은 급한 사건이 아니다.
    비율을 셀 날이 SPIKE_PREV 개도 안 되면 그 지수는 cut 를 None(못 쟀다)으로 둔다 — 0 이나 「튄 날 없음」 으로 내지 않는다."""
    cut, n, days = {}, {}, []
    for k in SPIKE_NAMES:
        s = [p for p in X.get(k) or [] if p[1] is not None]
        r = []
        for i in range(SPIKE_PREV, len(s)):
            m = sum(p[1] for p in s[i - SPIKE_PREV:i]) / SPIKE_PREV
            if m > 0:
                r.append((s[i][0], s[i][1], s[i][1] / m))
        n[k] = len(r)
        if len(r) < SPIKE_PREV:
            cut[k] = None
            continue
        q = sorted(x[2] for x in r)
        c = q[max(0, math.ceil(len(q) * (1 - SPIKE_TOP)) - 1)]   # 위 5% 의 경계 = 아래에서 95% 자리 값
        cut[k] = round(c, 2)
        days += [[d, k, v, round(x, 2)] for d, v, x in r if x >= c]
    days.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {"rule": "그날 값 ÷ 앞 %d개 값 평균이 받은 기간 안에서 위 %d%% 이상인 날 · 오른 쪽만 · 지수마다 따로" % (SPIKE_PREV, round(SPIKE_TOP * 100)),
            "names": SPIKE_NAMES, "cut": cut, "n": n, "days": days}


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
    X["spikes"] = spikes(X)
    X["errors"] = err
    X["src"] = "지정학 위험 Caldara · Iacoviello(matteoiacoviello.com · 100 = 1985~2019 평균) · 정책 불확실성 Baker · Bloom · Davis(policyuncertainty.com · 100 = 1985~2009 평균) · 무역정책 불확실성 Caldara 외 · VIX · OVX FRED"
    save(X, OUT, list(err), separators=(",", ":"))
    last = lambda s: s[-1] if s else "—"
    print("지정학 %s · 한국 달 %s · 정책 %s · 무역 %s · VIX %s · OVX %s · 큰 사건 %d · 튄 날 %d(경계 %s) · 못 받은 것 %s" % (
        last(X["gpr"]), last(X["gprMonthly"]), last(X["epu"]), last(X["tpu"]), last(X["vix"]), last(X["ovx"]), len(X["gprEvents"]), len(X["spikes"]["days"]),
        " ".join("%s %s" % (k, "—" if c is None else c) for k, c in X["spikes"]["cut"].items()), ", ".join(err) or "없음"))
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
