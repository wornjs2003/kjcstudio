# -*- coding: utf-8 -*-
"""PC 가 살아 있다는 신호를 Cloudflare KV 에 쓴다 (2026-09-23 지시).

재권님 말씀 그대로다.

    pc는 항상 켜져있는걸 전제로 해야하고
    꺼지거나 이슈가 있으면 알림이 오면 될거같은데

**꺼진 PC 는 자기가 꺼졌다고 못 알린다.** 그래서 밖에서 본다 —
이 파일이 5분마다 「살아 있다 + 내 상태」 를 KV 에 쓰고, 배포본 워커가
Cron 에서 그것을 읽어 **끊겼으면** 텔레그램으로 알린다.

**왜 KV 에 직접 쓰나** — 배포본은 Cloudflare Access 뒤라
`https://thekjcstudio.com/api/*` 를 부르면 **302**(로그인 화면으로 보냄)가
된다(2026-09-23 실측). `api.cloudflare.com` 은 Access 와 무관하다.
재권님이 (가)서비스 토큰 · (나)경로 Bypass · (다)KV 직접 셋 중
**(다)** 로 정하셨다 — Access 설정을 안 건드리는 쪽이다.

**상태를 함께 싣는 것이 핵심이다.** 그러면 「안 왔다(꺼짐)」 와
「왔는데 나쁘다(이슈)」 를 **한 경로로** 본다. 알림 길을 여럿 만들 필요가 없다.
"""

import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
API = "https://api.cloudflare.com/client/v4"

# 신호를 쓰는 주기. 워커 Cron 이 5분마다 도니 그것과 맞춘다.
BEAT_SEC = 300

# KV 키 하나에 **덮어쓴다.** 쌓지 않는다 — 마지막 것만 있으면 된다.
# 워커가 `env.KIS_KV.get(ALIVE_KEY)` 로 읽는다.
ALIVE_KEY = "alive:main"

# 신호가 이만큼 안 오면 워커가 「꺼졌다」 로 본다.
#
# **판정은 워커가 한다.** 여기 두는 것은 `worker/kis-worker.js` 의 같은 이름과
# **짝을 맞추기 위해서다** — `tools/check-kis-consts.py` 가 본다. 한쪽만 고치면
# 로컬 화면과 실제 알림이 갈리는데, 그때는 **알림이 안 오는 쪽으로** 갈려서
# 가장 조용하다.
#
# ⚠️ **지금은 시험 1단계 값(24시간)이다.** 값이 KV 에 제대로 쌓이는지만 보려는
# 것이라 **알림이 한 번도 안 간다.** 확인되면 2단계에서 **900(15분)** 으로 내린다.
ALIVE_STALE_SEC = 86400

# ── 「낡은 코드」 판정 범위 ──
#
# **`holdings/server/` 안에서만 센다.** 2026-09-23 에 이 범위를 안 좁히고
# 재다가 **헛알림을 한 번 냈다** — 서버가 10:06:57 에 떴고 HEAD 커밋이
# 10:08:18 이라 「낡았다」 로 읽었는데, **그 커밋은 서버 파일이 아니었다.**
# 좁혀 세니 0건이었다.
#
# 문서·화면 커밋마다 울리면 알림이 시끄러워져 정작 볼 것이 묻힌다.
STALE_PATHS = ["holdings/server/"]

# 그 위에 얹는 유예. 푸시 직후에는 늘 뒤처져 있으므로 바로 울리지 않는다.
STALE_GRACE_SEC = 1800          # 30분

_state = {"acc": None, "ns": None, "started_at": None, "last_err": None}


# ---------------------------------------------------------------- 설정

def _cf_config(proxy):
    """`secrets.json` 의 `cloudflare` 를 읽는다. 없으면 None.

    **`proxy.load_secrets()` 를 쓰지 않는다.** 그 함수는 이름과 달리
    **`kis` 항목만** 돌려준다 — 처음에 전체를 준다고 짐작하고 썼다가
    실제로 불러 보고 잡았다 (2026-09-23). 여기서는 파일을 직접 읽는다.
    """
    try:
        with io.open(proxy.SECRETS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    cf = (data or {}).get("cloudflare") or {}
    tok = (cf.get("api_token") or "").strip()
    if not tok:
        return None
    return {"token": tok, "account_id": (cf.get("account_id") or "").strip()}


def _api(cfg, path, method="GET", body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=body.encode("utf-8") if body else None)
    req.add_header("Authorization", "Bearer " + cfg["token"])
    if body is not None:
        req.add_header("Content-Type", "text/plain; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=20) as f:
            return f.status, json.load(f)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, {"_err": type(e).__name__}


def _resolve(cfg):
    """계정 ID 와 저장 공간 ID 를 한 번만 찾아 둔다.

    **첫 번째 것을 고르지 않는다.** 계정이 둘 이상이면 멈추고 알린다 —
    조용히 엉뚱한 곳에 쓰는 것이 가장 나쁘다 (2026-09-23 지시).
    `secrets.json` 에 `account_id` 가 있으면 **그것을 먼저 쓴다.**
    """
    acc = cfg.get("account_id")
    if not acc:
        code, body = _api(cfg, "/accounts?per_page=50")
        rows = (body or {}).get("result") or []
        if code != 200 or not rows:
            return None, "계정 목록을 못 받았습니다 (HTTP %s)" % code
        if len(rows) > 1:
            return None, ("계정이 %d개입니다 — `secrets.json` 의 cloudflare 에 "
                          "\"account_id\" 를 정해 주십시오" % len(rows))
        acc = rows[0]["id"]

    code, body = _api(cfg, "/accounts/%s/storage/kv/namespaces?per_page=100" % acc)
    rows = (body or {}).get("result") or []
    if code != 200 or not rows:
        return None, "저장 공간 목록을 못 받았습니다 (HTTP %s)" % code
    if len(rows) > 1:
        # 워커가 쓰는 것을 고른다 — `token:` 키가 들어 있는 쪽이다.
        for r in rows:
            c, b = _api(cfg, "/accounts/%s/storage/kv/namespaces/%s/keys?limit=100"
                        % (acc, r["id"]))
            names = [k.get("name", "") for k in ((b or {}).get("result") or [])]
            if any(n.startswith("token:") for n in names):
                return {"acc": acc, "ns": r["id"]}, None
        return None, "저장 공간이 %d개인데 어느 것인지 못 갈랐습니다" % len(rows)
    return {"acc": acc, "ns": rows[0]["id"]}, None


# ---------------------------------------------------------------- 상태 모으기

def _stale_commits(started_at):
    """서버가 뜬 뒤에 **서버 파일**이 바뀐 커밋 수. git 이 없으면 None."""
    if not started_at:
        return None
    try:
        since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_at))
        out = subprocess.run(
            ["git", "log", "--since=" + since, "--oneline", "--"] + STALE_PATHS,
            cwd=REPO, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return None
        return len([x for x in (out.stdout or "").splitlines() if x.strip()])
    except Exception:
        return None


def _daily_today(now=None):
    """오늘 데일리분석이 저장됐나. **결과물을 본다.**

    `daily.py` 는 실패를 콘솔에만 적는다 — 그 변수는 메모리 안이라 밖에서
    못 읽는다. 그래서 **남은 파일**을 본다. 스스로 신고하는 것이 아니라
    결과를 보는 쪽이라, `daily.py` 를 건드리지 않아도 된다.
    """
    try:
        import docstore
        day = time.strftime("%Y%m%d", time.localtime(now or time.time()))
        return os.path.exists(os.path.join(docstore.DOC_ROOT, "daily-%s.json" % day))
    except Exception:
        return None


def collect(proxy):
    """신호에 실을 것을 모은다. **하나가 실패해도 나머지는 간다.**"""
    now = time.time()
    out = {
        "ts": int(now),
        "startedAt": int(_state["started_at"] or now),
        "port": getattr(proxy, "MAIN_PORT", None),
    }

    # `/api/kis/health` 가 하는 것과 같다 — 부르고 안 죽으면 살아 있는 것이다.
    # `get_token()` 은 캐시를 보므로 5분마다 불러도 새로 발급하지 않는다.
    try:
        cfg = proxy.load_secrets()
        if not cfg:
            out["tokenOk"] = None          # 열쇠가 없는 서버다 — 「나쁨」 이 아니다
        else:
            proxy.get_token(cfg)
            out["tokenOk"] = True
    except Exception:
        out["tokenOk"] = False

    try:
        import dart
        out["dartLastPoll"] = dart._meta_get("dart_last_poll") or None
        out["dartLastError"] = (dart._meta_get("dart_last_error") or "")[:120] or None
    except Exception:
        out["dartLastPoll"] = out["dartLastError"] = None

    # **`last_collected_at()` 같은 함수는 없다.** 처음에 그 이름을 지어 썼다가
    # 실제로 세어 보고 잡았다. `total()` 이 주는 `to` 가 **가장 최근 뉴스 시각**이고,
    # 수집이 멈추면 그 값이 안 움직인다.
    try:
        import news_store
        t = news_store.total() or {}
        out["newsLastAt"] = t.get("to")
        out["newsCount"] = t.get("count")
    except Exception:
        out["newsLastAt"] = out["newsCount"] = None

    out["dailyToday"] = _daily_today(now)
    out["staleCommits"] = _stale_commits(_state["started_at"])
    out["staleGraceSec"] = STALE_GRACE_SEC
    return out


# ---------------------------------------------------------------- 쓰기

def beat_once(proxy, cfg):
    payload = json.dumps(collect(proxy), ensure_ascii=False)
    path = "/accounts/%s/storage/kv/namespaces/%s/values/%s" % (
        _state["acc"], _state["ns"], urllib.parse.quote(ALIVE_KEY, safe=""))
    code, body = _api(cfg, path, "PUT", payload)
    return code == 200 and (body or {}).get("success") is True, code


def start(proxy, port):
    """서버가 뜰 때 부른다. 돌기 시작하면 True.

    **메인 포트에서만 돈다.** 폴더가 여섯이고 `secrets.json` 도 여섯인데
    KV 키는 **하나**다. 여럿이 쓰면 **메인이 꺼져도 세션 서버가 덮어써서
    알림이 안 온다** — 막으려던 것의 반대가 된다.
    """
    if port != getattr(proxy, "MAIN_PORT", 8765):
        return False

    try:
        cfg = _cf_config(proxy)
    except Exception:
        cfg = None
    if not cfg:
        return False

    found, err = _resolve(cfg)
    if not found:
        print("  [살아있음] 못 켰습니다 — %s" % err, flush=True)
        return False
    _state["acc"], _state["ns"] = found["acc"], found["ns"]
    _state["started_at"] = time.time()

    def loop():
        time.sleep(10)      # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
                ok, code = beat_once(proxy, cfg)
                key = None if ok else "HTTP %s" % code
            except Exception as e:
                key = "%s: %s" % (type(e).__name__, e)
            # **같은 오류는 한 번만 적는다.** `daily.py` 와 같은 꼴이다 —
            # 5분마다 적으면 하루 이백 줄이 쌓여 다른 줄이 묻힌다.
            if key != _state["last_err"]:
                _state["last_err"] = key
                if key:
                    print("  [살아있음] 못 보냈습니다 — %s" % key, flush=True)
                    print("    (같은 오류는 다시 안 적습니다. 5분마다 계속 시도합니다)",
                          flush=True)
                else:
                    print("  [살아있음] 다시 보내지고 있습니다", flush=True)
            time.sleep(BEAT_SEC)

    threading.Thread(target=loop, daemon=True, name="heartbeat").start()
    return True
