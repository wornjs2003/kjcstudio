# -*- coding: utf-8 -*-
"""슬랙 연결 — 이 컴퓨터의 봇으로 거래 채널을 읽고(conversations.history) 결과를 쓴다(chat.postMessage) (2026-11-23 · 개발2).

컴퓨터마다 슬랙 앱(봇)을 따로 — 한 앱을 여럿이 쓰면 메시지가 한 대에만 가는 일이 생긴다(슬랙 문서 소켓 모드 「each payload may be sent to any of the connections」).
받는 길은 소켓 모드 대신 READ_SEC 마다 채널 읽기 — 표준 부품만으로 되고(실행 파일에 부품을 더 안 넣음) · 끊겼다 붙어도 마지막 본 ts 뒤를 그대로 메움(qa 9) ·
conversations.history 는 분당 50회 넘게 되는 등급(Tier 3 · 슬랙 문서)이라 READ_SEC 2 면 분당 30회.
봇 권한 — channels:history(공개 채널) · groups:history(비공개 채널) · chat:write.
"""
import json
import time
import urllib.parse
import urllib.request

API = "https://slack.com/api/"
READ_SEC = 2


class SlackError(Exception):
    pass


class Slack:
    def __init__(self, bot_token, channel_id):
        self.tok, self.ch = bot_token, channel_id

    def _get(self, method, params):
        req = urllib.request.Request(API + method + "?" + urllib.parse.urlencode(params), headers={"Authorization": "Bearer " + self.tok})
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        if not j.get("ok"):
            raise SlackError(str(j.get("error"))[:60])
        return j

    def read_since(self, oldest):
        """oldest(ts 글) 뒤 메시지 — 오래된 것부터 [(ts, text)] · 처음(oldest None)은 지금부터."""
        if oldest is None:
            return [], "%.6f" % time.time()
        out, cursor = [], None
        for _ in range(10):
            q = {"channel": self.ch, "oldest": oldest, "limit": 200}
            if cursor:
                q["cursor"] = cursor
            j = self._get("conversations.history", q)
            out += [(m.get("ts"), m.get("text") or "") for m in j.get("messages") or []]
            cursor = (j.get("response_metadata") or {}).get("next_cursor")
            if not j.get("has_more") or not cursor:
                break
        out.sort(key=lambda x: float(x[0]))
        return out, (out[-1][0] if out else oldest)

    def post(self, text):
        body = json.dumps({"channel": self.ch, "text": text}).encode("utf-8")
        req = urllib.request.Request(API + "chat.postMessage", data=body,
                                     headers={"Authorization": "Bearer " + self.tok, "Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        if not j.get("ok"):
            raise SlackError(str(j.get("error"))[:60])
