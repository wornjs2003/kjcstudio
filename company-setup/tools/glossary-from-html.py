#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시황분석1 용어집(temp/시황분석1-glossary.html · 조사 결과 · 저장소 밖)을 company-setup/data/glossary.json 한 곳으로 옮긴다.
   문서(analysis.html)는 js/glossary.js 로 이 JSON 을 읽어 낱말에 풍선을 단다 — 용어 · 뜻 · 출처가 두 곳이 되지 않게 이 파일만이 원천이다.
   쓰는 법: python3 company-setup/tools/glossary-from-html.py [temp/시황분석1-glossary.html]
   (2026-10-07 재권님 「용어집을 종목분석에 있는 말이 있으면 마우스 올리면 설명으로 뜨도록 · 없으면 같이 있어도 되는 칸 찾아서 용어 넣고 설명」)"""
import sys, re, json, html, io, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "temp", "시황분석1-glossary.html")
out = os.path.join(ROOT, "company-setup", "data", "glossary.json")
s = open(src, encoding="utf-8").read()
def txt(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()
# 낱말 → 문서에서 찾을 글자들(짧은 한글은 조사가 붙어도 찾게 js 쪽이 처리한다)
MATCH = {
  "매물대": ["매물대"],
  "지지선 · 저항선": ["1차 지지", "2차 지지", "1차 저항", "2차 저항", "지지선", "저항선", "지지구간", "저항구간", "지지", "저항"],
  "ZigZag(꺾임점 · 스윙 고점/저점)": ["ZigZag", "꺾임점", "꺾임"],
  "손절가 · 목표가 · 매수가 · 손익비": ["손절가", "목표가", "매수가", "손익비", "손절"],
  "눌림(눌림목) · 분할 매수 · 관망 · 보류 · 비중 축소 · 버퍼": ["눌림목", "눌림", "분할 매수", "관망", "보류", "비중 축소", "버퍼"],
  "이동평균(선)": ["이동평균선", "이동평균", "이평선", "MA5", "MA20", "MA60", "MA112", "MA224", "MA448", "224일선", "224선"],
  "골든크로스 · 데드크로스": ["골든크로스", "데드크로스", "골든", "데드"],
  "정배열 · 역배열": ["정배열", "역배열"],
  "RSI": ["RSI"], "MACD": ["MACD"], "볼린저 밴드(%B)": ["볼린저", "%B"], "스토캐스틱": ["스토캐스틱"],
  "ADX(+DI · −DI)": ["ADX", "+DI", "−DI", "DMI"], "ATR": ["ATR"], "OBV": ["OBV"],
  "일목균형표(전환 · 기준 · 선행 · 구름)": ["일목균형표", "일목", "구름"],
  "VWAP": ["VWAP"], "상대수익률(지수 대비)": ["상대수익률"],
  "PER": ["추정 PER", "PER 밴드", "PER"], "PBR · BPS": ["PBR", "BPS"], "EPS": ["추정 EPS", "EPS"], "ROE": ["ROE"],
  "영업이익률 · 순이익률": ["영업이익률", "순이익률"], "부채비율": ["부채비율"], "시가총액": ["시가총액"], "공매도": ["공매도"],
  "컨센서스 · 증권사 목표주가 · 투자의견": ["컨센서스", "증권사 목표주가", "목표주가", "투자의견"],
  "수급(외국인 · 기관 순매수) · 영업이익 YoY · PER 밴드": ["영업이익 YoY", "순매수", "수급"],
}
items = []; group = None
for m in re.finditer(r'<h2[^>]*>(.*?)</h2>|<article([^>]*)>(.*?)</article>', s, re.S):
    if m.group(1) is not None: group = txt(m.group(1)); continue
    a = m.group(3); cls = m.group(2) or ""
    h3 = txt(re.search(r"<h3>(.*?)</h3>", a, re.S).group(1))
    kv = {txt(k): txt(v) for k, v in re.findall(r'<div class="kv"><span>(.*?)</span>(.*?)</div>', a, re.S)}
    quotes = []
    for q, src_ in re.findall(r"<blockquote>(.*?)</blockquote>\s*<div class=\"src\">(.*?)</div>", a, re.S):
        am = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', src_, re.S)
        quotes.append({"text": txt(q), "source": txt(am.group(2)).rstrip(" ›") if am else txt(src_), "url": am.group(1) if am else None})
    none = re.search(r'<div class="none">(.*?)</div>', a, re.S)
    note = [txt(n) for n in re.findall(r'<p class="note">(.*?)</p>', a, re.S)]
    items.append({"id": h3, "term": kv.get("우리가 쓸 낱말", h3), "aliases": kv.get("다른 이름", ""), "group": group,
                  "quotes": quotes, "missing": txt(none.group(1)) if none else None, "weak": "weak" in cls,
                  "cell": kv.get("리포트 칸", ""), "note": note, "match": MATCH.get(h3, [h3])})
doc = {"_읽는법": "종목 분석 문서의 용어 풍선 재료 — js/glossary.js 가 읽는다. 원천은 시황분석1 조사(temp/시황분석1-glossary.html · 2026-10-07)이고 이 파일로 옮긴 것이 저장소의 한 곳이다. quotes = 출처 문장 그대로(번역 안 함) · missing = 권위 출처 못 찾음(우리 정의) · weak = 원문을 직접 못 열어 본 것 · match = 문서에서 찾을 글자(긴 것부터). 값을 고치려면 이 파일만.",
       "from": os.path.relpath(src, ROOT), "madeAt": re.search(r"조사 · ([0-9\-]+ [0-9:x]+)", s).group(1) if re.search(r"조사 · ([0-9\-]+ [0-9:x]+)", s) else "", "items": items}
json.dump(doc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
miss = [i["id"] for i in items if i["missing"]]
print(f"{len(items)}개 → {os.path.relpath(out, ROOT)} · 출처 못 찾음 {len(miss)} · 인용 {sum(len(i['quotes']) for i in items)}")
for i in items:
    if i["id"] not in MATCH: print("  match 없음(제목 그대로):", i["id"])
