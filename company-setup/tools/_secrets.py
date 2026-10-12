"""열쇠 파일 자리 — company-setup/tools 의 받는 도구가 함께 쓴다(2026-10-12 재권님 「열쇠파일은 한자리로 모아 · 한벌로」 · 창구 경유).

    KJC_SECRETS 환경변수가 있으면 그것 → ~/.kjc/secrets.json 이 있으면 그것 → 없으면 옛 자리(저장소 holdings/secrets.json)

서버 쪽(holdings/server)과 같은 순서다. 이 셈은 여기 한 곳 — 도구마다 경로를 박지 않는다.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def secrets_path():
    env = os.environ.get("KJC_SECRETS")
    if env:
        return env
    home = os.path.join(os.path.expanduser("~"), ".kjc", "secrets.json")
    if os.path.exists(home):
        return home
    return os.path.join(ROOT, "holdings", "secrets.json")
