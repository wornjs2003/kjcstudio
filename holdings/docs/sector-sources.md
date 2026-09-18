# 「지금 뜨는 산업」 — 어디서 받을 수 있나

2026-09-18 `홈페이지_정리` 조사. **전부 실제로 호출해서 확인한 값이다.**
확인하지 못한 것은 그렇게 적었다.

`kis-sector-investor.md` 가 KIS 쪽을 이미 다 정리해 두었다. 이 문서는
**그 밖의 곳**과 **같은 값을 두 곳에서 받을 수 있는지**를 본다.

---

## 0. 한눈에

| 무엇 | KIS | 네이버(비공식) | 그 밖 |
|---|---|---|---|
| **업종 등락률** | 있다 · 38개 | **있다 · 79개** | 실시간으로 주는 곳 없음 |
| **테마 등락률** | **없다** | 있다 · 264개 | 없음 |
| **업종·테마의 구성종목** | — | **있다** | — |

**업종은 두 곳에서 받을 수 있고, 테마는 네이버 한 곳뿐이다.**

---

## 1. 업종 — 두 곳의 기준이 다르다

| | KIS | 네이버 |
|---|---|---|
| 개수 | **38** | **79** |
| 분류 | 거래소가 정한 표준 업종 | 네이버 자체 분류 |
| 성격 | 공식 | 비공식 |

**둘은 서로의 대체가 아니다.** 같은 시장을 다른 자로 잰 것이라, 한쪽이
죽었을 때 다른 쪽으로 갈아끼우면 화면의 항목 수와 이름이 통째로 바뀐다.
**이중화(같은 값을 두 곳에서)가 아니라 두 가지 보기로 쓰는 편이 맞다.**

### 네이버 업종 목록

    GET https://m.stock.naver.com/api/stocks/industry?page=1&pageSize=5

응답 (2026-09-18 장중 실측, 한 항목만 옮김):

```json
{ "stockListSortType": "INDUSTRY",
  "groups": [
    { "no": 293, "name": "통신장비", "totalCount": 55,
      "changeRate": "4.68", "riseCount": 36, "fallCount": 9, "steadyCount": 10 }
  ],
  "totalCount": 79, "page": 1, "pageSize": 5,
  "marketStatus": "OPEN" }
```

- **기본이 등락률 내림차순**이다. 「지금 뜨는」 순서가 그대로 온다
- `riseCount` · `fallCount` · `steadyCount` — **그 업종 안에서 몇이 오르고
  내렸는지**가 같이 온다. KIS 업종 API 에는 없는 값이다
- `marketStatus` 로 장이 열려 있는지 알 수 있다
- 정렬 파라미터(`sortType` · `sortOrder`)를 넣어봤지만 **기본과 같은 결과**였다.
  파라미터가 먹는 것인지 원래 그 순서인지는 **가리지 못했다**

### 네이버 테마 목록

    GET https://m.stock.naver.com/api/stocks/theme?page=1&pageSize=5

`totalCount` **264**. 응답 모양은 업종과 똑같다(`stockListSortType` 이
`THEME` 인 것만 다르다). 「뉴로모픽 반도체」 「스페이스X」 같은 묶음이 온다.

**KIS 에는 테마가 없다.** 근거는 `kis-sector-investor.md` 5절에 있다.

---

## 2. 구성종목까지 내려간다 (2026-09-18 새로 확인)

목록에서 받은 `no` 를 그대로 붙이면 그 묶음의 종목이 온다.

    GET https://m.stock.naver.com/api/stocks/industry/{no}?page=1&pageSize=3
    GET https://m.stock.naver.com/api/stocks/theme/{no}?page=1&pageSize=3

응답의 `stocks[]` 한 항목이 갖고 있는 것:

    stockType · stockEndType · itemCode · reutersCode · stockName · sosok
    closePrice · compareToPreviousClosePrice · compareToPreviousPrice
    fluctuationsRatio · accumulatedTradingVolume · accumulatedTradingValue

**현재가 · 전일대비 · 등락률 · 누적거래량 · 누적거래대금이 한 번에 온다.**
업종을 눌러 종목을 펼치는 화면을 이것 하나로 만들 수 있다.

`{no}/stocks` 는 `404` 다. `{no}` 로 끝나야 한다.

---

## 3. 안 되거나 안 맞는 곳

| 출처 | 결과 | 왜 |
|---|---|---|
| **다음 금융** `finance.daum.net/api/sectors` · `/api/themes` | **500(서버가 터짐)** | `Referer` 를 붙여도 같다. 다른 경로가 있는지는 확인 못 했다 |
| **공공데이터포털** 금융위 주식·지수시세 | 쓸 수 없다 | **하루 1회 갱신 · 기준일 다음 영업일 오후 1시 이후.** 「지금」 이 아니다 |
| **KRX Open API** | 쓸 수 없다 | 일별 시세·지수만. 실시간이 아니다 |
| **KRX 정보데이터시스템** `data.krx.co.kr` | `302`(다른 주소로 보냄) | OTP 를 먼저 받아 POST 하는 방식이라 손이 많이 간다. 파보지 않았다 |

---

## 4. 확인하지 못한 것

- **Cloudflare Worker 에서 네이버 주소가 열리는지 못 봤다.** 엣지 IP 가
  막힐 수 있다. 로컬(`kis_proxy.py`)에서는 된다. **붙이기 전에 워커에서
  한 번 불러봐야 한다** — 이것이 가장 큰 미확인 항목이다
- 네이버 쪽 **호출 한도**. 공개된 것이 없다
- 네이버 업종 79개와 KIS 업종 38개의 **이름 대응표**. 만들지 않았다
- FnGuide · 팍스넷 등 다른 곳

---

## 5. 붙인다면

`server/dart.py` 가 시가총액 순위·지수 구성종목을 받을 때 쓰는 것과
**같은 계통**(`m.stock.naver.com/api/...`)이라, 이 저장소가 이미 쓰고 있는
방식이다. `data-sources.md` 의 「공식과 비공식을 갈라두는 이유」 를 따르면
업종·테마는 **판단에 직결되는 값이 아니라 보조 정보**라 비공식으로 받아도
되는 쪽이다.

**다만 화면에 어느 쪽 기준인지 적어야 한다.** 업종이 38개인 화면과 79개인
화면이 같은 이름을 달고 있으면, 보는 쪽은 숫자가 왜 다른지 알 수 없다.
