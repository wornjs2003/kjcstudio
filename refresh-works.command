#!/bin/bash
# KJC Studio · 작업물 데이터 갱신
# 더블클릭하면 assets/images/works/<카테고리>/ 폴더를 스캔해서 data/works.json 을 자동 업데이트합니다.
# 새 이미지를 해당 카테고리 폴더에 드롭한 뒤 이 파일을 더블클릭하세요.
# 종료: 이 창을 닫거나 Enter

cd "$(dirname "$0")"

echo "────────────────────────────────────────────"
echo "  KJC Studio · 작업물 데이터 갱신"
echo "────────────────────────────────────────────"
echo ""
echo "  스캔 폴더:"
echo "    · assets/images/works/3d-modeling/"
echo "    · assets/images/works/ai-work/"
echo "    · assets/images/works/web-interactive/"
echo "    · assets/images/works/branding/"
echo ""

python3 tools/refresh-works.py
RC=$?

echo "────────────────────────────────────────────"
if [ $RC -eq 0 ]; then
  echo "  완료. 브라우저에서 새로고침해서 확인하세요."
else
  echo "  ⚠ 오류 발생 (exit code $RC)"
fi
echo ""
read -n 1 -s -r -p "  Enter 또는 아무 키 눌러서 종료..."
echo ""
