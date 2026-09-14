#!/bin/bash
cd "$(dirname "$0")"
python3 server/setup_dart.py
echo
read -n 1 -s -r -p "아무 키나 누르면 닫힙니다..."
