#!/bin/bash
# KJC Studio - QA 보드 (포트 8093)
# server.py 가 저장소 루트를 내보낸다. 화면이 ../assets/ 를 함께 쓰기 때문이다.
cd "$(dirname "$0")"

lsof -ti tcp:8093 | xargs kill -9 2>/dev/null

python3 server.py
