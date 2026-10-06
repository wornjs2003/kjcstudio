# holdings/worker — 꺼짐 감시 워커 하나

- `heartbeat-watch.js` 를 Cloudflare 워커 **kjc-kis-kv** 에 붙여 넣는다(Edit code → 전부 지우고 붙여 넣기 → Deploy · 끝이 `};` 인지 본다). 요청은 맥미니로 그대로 넘기고, Cron(5분)마다 맥미니 신호(KV `alive:main`)를 읽어 꺼지거나 고장이 나면 텔레그램으로 한 번 알린다 — 2026-10-06 재권님 「ㄴ」.
- 꺼졌다고 보는 기준(초)은 `holdings/server/heartbeat.py` 의 `ALIVE_STALE_SEC` 한 곳에 있고, 신호에 실려 워커로 간다.
- 되돌리기: 옛 전체 워커는 git 이력의 `holdings/worker/kis-worker.js`(커밋 4651907 직전).
