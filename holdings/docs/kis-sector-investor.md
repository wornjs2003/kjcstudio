# 업종 · 순위 · 투자자 — KIS 에서 무엇을 어떻게 받나

첫 화면의 두 칸이 쓰는 자료입니다.

    지금 뜨는 산업      업종 등락률 · 상승률 TOP · 테마
    외국인 · 기관 매매   순매수 상위 · 30일 추이

**여기 적힌 `tr_id` · 경로 · 파라미터 · 필드 이름은 2026-09-17 에 실전투자
계정으로 직접 호출해 받은 값입니다.** 문서에서 옮겨 적은 것이 아닙니다.
확인하지 못한 것은 맨 아래 「확인하지 못한 것」 에 따로 모아 두었습니다.

> **왜 이 파일을 만들었나** — 2026-09-16 에 같은 조사를 했는데 값을 남기지
> 않아 다음 날 처음부터 다시 했습니다. `tr_id` 하나, 파라미터 한 칸을
> 못 찾아 헤매는 시간이 조사 전체보다 깁니다.

---

## 0. 한눈에

| 무엇 | KIS 경로 | `tr_id` | 한 번에 오는 양 |
|---|---|---|---|
| 업종 등락률 | `/uapi/domestic-stock/v1/quotations/inquire-index-category-price` | `FHPUP02140000` | 시장 하나당 전 업종 |
| 등락률 순위 | `/uapi/domestic-stock/v1/ranking/fluctuation` | `FHPST01700000` | 30행 (고정) |
| 투자자 일별 추이 | `/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market` | `FHPTJ04040000` | 300영업일 |
| 순매수 상위 | `/uapi/domestic-stock/v1/quotations/foreign-institution-total` | `FHPTJ04400000` | 30행 (고정) |
| 종목별 투자자 | `/uapi/domestic-stock/v1/quotations/inquire-investor` | `FHKST01010900` | 30일 |
| **테마** | **없습니다** | — | — |

---

## 1. 업종 등락률

    경로   /uapi/domestic-stock/v1/quotations/inquire-index-category-price
    tr_id  FHPUP02140000

| 파라미터 | 넣는 값 |
|---|---|
| `FID_COND_MRKT_DIV_CODE` | `U` (업종) |
| `FID_COND_SCR_DIV_CODE` | `20214` |
| `FID_INPUT_ISCD` | `0001` 코스피 · `1001` 코스닥 — **`output1`(머리글 지수)만 정한다** |
| `FID_MRKT_CLS_CODE` | `K` 코스피 · `Q` 코스닥 — **목록을 정하는 것은 이쪽이다** |
| `FID_BLNG_CLS_CODE` | 아래 표 |

### `FID_BLNG_CLS_CODE` — 네 값을 다 불러봤습니다

공식 문서에 값이 적혀 있지 않아 0·1·2·3 을 직접 넣어 확인했습니다.

| 값 | `K`(코스피) | `Q`(코스닥) |
|---|---|---|
| `0` | 38행 — 업종 + 대형주 + 파생지수가 섞임 | 100행 — **거의 다 파생지수**. 쓸 수 없다 |
| `1` | 4행 — 고배당50 · 배당성장50 · 우선주 · VKOSPI | 23행 — 중형주 · KSQ150 계열 |
| `2` | 4행 — 종합 · 대형주 · 중형주 · 소형주 | 0행 |
| `3` | **26행 — 업종** | **17행 — 업종** |

**`3` 이 업종(산업별)입니다.** 이것을 씁니다.

### 국내 업종은 몇 개인가 — 직접 세었습니다 (2026-09-17)

**41개입니다.** 코스피 24 · 코스닥 17.

`blng=3` 이 코스피에서 26행을 주는데, 그중 둘은 업종이 아니라 지수 상품입니다.

    0244  코스피200제외 코스피지수
    2283  코스피 200 기후변화지수

「지금 뜨는 산업」 에 이것이 올라오면 안 되므로 서버·워커의 `SECTOR_SKIP` 에서
빼고 있습니다. **코스닥 쪽은 깨끗합니다** (17행 전부 업종).

> `SECTOR_SKIP` 은 서버와 워커 두 곳에 있는 복제라
> `holdings/tools/check-kis-consts.py` 가 대조합니다. 값을 고칠 때 한쪽만
> 고치면 거기서 걸립니다.

**코스피 24 (`0005`~`0030`)**

    0005 음식료·담배   0006 섬유·의류    0007 종이·목재    0008 화학
    0009 제약          0010 비금속       0011 금속         0012 기계·장비
    0013 전기·전자     0014 의료·정밀기기 0015 운송장비·부품 0016 유통
    0017 전기·가스     0018 건설         0019 운송·창고     0020 통신
    0021 금융          0024 증권         0025 보험         0026 일반서비스
    0027 제조          0028 부동산       0029 IT 서비스     0030 오락·문화

`0022` · `0023` 은 **오지 않습니다.** 왜 비어 있는지는 확인하지 못했습니다.

**코스닥 17 (`1006`~`1031`)**

    1006 일반서비스   1011 유통        1013 운송·창고    1014 금융
    1019 음식료·담배  1020 섬유·의류    1021 종이·목재    1022 출판·매체복제
    1023 화학        1024 제약        1025 비금속       1026 금속
    1027 기계·장비    1028 전기·전자    1029 의료·정밀기기 1030 운송장비·부품
    1031 기타제조

번호가 띄엄띄엄합니다. **목록을 코드로 박아 두지 말고 매번 받아 씁니다** —
분기마다 KRX 가 업종을 개편하므로 박아 두면 그때 갈립니다.

### `output2` 필드 (실제 한 행, 2026-09-17 장 마감 뒤)

```json
{ "bstp_cls_code": "0015", "hts_kor_isnm": "운송장비·부품",
  "bstp_nmix_prpr": "4710.23", "bstp_nmix_prdy_vrss": "110.40",
  "prdy_vrss_sign": "2", "bstp_nmix_prdy_ctrt": "2.40",
  "acml_vol": "9163", "acml_tr_pbmn": "1275558",
  "acml_vol_rlim": "4.15", "acml_tr_pbmn_rlim": "" }
```

| 필드 | 뜻 | 단위 |
|---|---|---|
| `bstp_cls_code` | 업종 코드 | |
| `hts_kor_isnm` | 업종 이름 | |
| `bstp_nmix_prpr` | 업종 지수 현재값 | pt |
| `bstp_nmix_prdy_vrss` · `bstp_nmix_prdy_ctrt` | 전일대비 · 등락률 | pt · % |
| `prdy_vrss_sign` | 1상한 2상승 3보합 4하한 5하락 | |
| `acml_vol` | 누적 거래량 | **천주** |
| `acml_tr_pbmn` | 누적 거래대금 | **백만원** |
| `acml_vol_rlim` | 시장 전체 거래량 중 비중 | % |
| `acml_tr_pbmn_rlim` | 거래대금 비중 — **빈 문자열로 옵니다** | |

**`acml_tr_pbmn_rlim` 은 늘 비어서 왔습니다.** 41행 전부 `""` 였습니다.
값을 안 주는 것인지 장 마감 뒤라 그런지는 확인하지 못했습니다.
쓰려면 `acml_tr_pbmn` 을 `output1` 의 것과 나눠 직접 계산해야 합니다.

**단위 근거** — `output1`(코스피 종합)의 `acml_tr_pbmn` 이 `17144039` 였습니다.
백만원으로 읽으면 17.1조원으로 코스피 하루 거래대금과 맞습니다.
`acml_vol` `221006` 도 천주로 읽으면 2.2억주입니다.

---

## 2. 등락률 순위 (상승률 TOP · 하락률 TOP)

    경로   /uapi/domestic-stock/v1/ranking/fluctuation
    tr_id  FHPST01700000

| 파라미터 | 넣는 값 |
|---|---|
| `fid_cond_mrkt_div_code` | `J` (KRX) |
| `fid_cond_scr_div_code` | `20170` — 다른 값을 넣으면 안 됩니다 |
| `fid_input_iscd` | `0000` 전체 · `0001` 코스피 · `1001` 코스닥 |
| `fid_rank_sort_cls_code` | `0` 상승률순 · `1` 하락률순 |
| `fid_prc_cls_code` | **`1` 종가(전일)대비.** 아래 함정 참조 |
| 나머지 8칸 | 빈 문자열 또는 `0` 으로 두면 전 종목 |

### ⚠️ `fid_prc_cls_code` 를 `0` 으로 두면 엉뚱한 줄이 섭니다

`0` 은 **저가대비** 상승률로 줄을 세웁니다. 그러면 1위가 이렇게 나옵니다.

    058110 멕아이씨에스   prdy_ctrt -0.73%   lwpr_vrss_prpr_rate 41.17%

**등락률이 마이너스인 종목이 「상승률 1위」 로 옵니다.** 저가에서 41% 올랐을
뿐 전일 대비로는 내린 종목입니다. `1`(종가대비)로 두어야 흔히 말하는
상승률 순위가 됩니다.

    fid_prc_cls_code = 1  →  042370 비츠로테크 +30.00%  (2026-09-17 1위)

이 값은 KIS 공식 예제에도 설명이 없어 **양쪽을 다 불러보고 골랐습니다.**

### 몇 개가 오나

**항상 30행입니다.** `fid_input_cnt_1` 에 `0`·`50`·`100` 을 넣어도 30행입니다.
그래서 서버의 `MOVERS_MAX` 가 30 입니다.

### 실측 (2026-09-17 마감 뒤)

    상승 전체    042370 비츠로테크 +30.00 | 348080 큐라티스 +29.96 | 051630 진양화학 +29.94
    상승 코스피  051630 진양화학 +29.94 | 002360 SH에너지화학 +28.46 | 480370 씨케이솔루션 +24.56
    상승 코스닥  042370 비츠로테크 +30.00 | 348080 큐라티스 +29.96 | 285800 진영 +29.93
    하락 전체    082660 코스나인 -33.33 | 475830 오름테라퓨틱 -29.98 | 001770 SHD -26.47

### 주요 필드

| 필드 | 뜻 |
|---|---|
| `stck_shrn_iscd` | 종목코드 6자리 |
| `hts_kor_isnm` | 종목명 |
| `data_rank` | 순위 |
| `stck_prpr` · `prdy_vrss` · `prdy_ctrt` | 현재가 · 전일대비 · 등락률 |
| `prdy_vrss_sign` | 부호 (위와 같음) |
| `acml_vol` | 거래량 (주) |
| `stck_hgpr` · `stck_lwpr` | 당일 고가 · 저가 |
| `lwpr_vrss_prpr_rate` | 저가대비 등락률 — `prc_cls_code=0` 이 이걸로 줄을 세운다 |

---

## 3. 시장 전체 투자자별 매매 — 30일 추이

    경로   /uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market
    tr_id  FHPTJ04040000

| 파라미터 | 넣는 값 |
|---|---|
| `FID_COND_MRKT_DIV_CODE` | `U` |
| `FID_INPUT_ISCD` | `0001` 코스피 · `1001` 코스닥 |
| `FID_INPUT_ISCD_1` | `KSP` 코스피 · `KSQ` 코스닥 |
| `FID_INPUT_ISCD_2` | 업종분류코드 — `FID_INPUT_ISCD` 와 같은 값을 넣었습니다 |
| `FID_INPUT_DATE_1` | **가장 최근 날짜** (YYYYMMDD) |
| `FID_INPUT_DATE_2` | 공식 설명이 「날짜1과 동일날짜 입력」 이라 같은 값을 넣습니다 |

### 한 번에 300영업일이 옵니다

`FID_INPUT_DATE_1` 에 `20260917` 을 넣으니 `20260917` 부터 **`20250630` 까지
300행**이 왔습니다. `20260818` 을 넣으니 거기서부터 300행이었습니다.
즉 **날짜1이 끝점이고 거기서 과거로 300영업일**입니다.

그래서 **30일 추이를 만드는 데 호출이 한 번**입니다. 날짜를 하루씩 30번
부를 필요가 없습니다.

`FID_INPUT_DATE_2` 를 다르게 넣어도 결과가 달라지지 않았습니다 — 무시되는
것으로 보이지만 **없으면 `OPSQ2001` 오류**가 납니다. 필수입니다.

### 실제 한 행 (2026-09-17 코스피)

```json
{ "stck_bsop_date": "20260917",
  "bstp_nmix_prpr": "6715.41", "bstp_nmix_prdy_vrss": "-2.56",
  "prdy_vrss_sign": "5", "bstp_nmix_prdy_ctrt": "-0.04",
  "frgn_ntby_qty": "-17243",  "frgn_ntby_tr_pbmn": "-2632088",
  "prsn_ntby_qty":  "7881",   "prsn_ntby_tr_pbmn":   "676052",
  "orgn_ntby_qty":  "5306",   "orgn_ntby_tr_pbmn":   "249709" }
```

| 앞머리 | 누구 |
|---|---|
| `prsn_` | 개인 |
| `frgn_` | 외국인 (`frgn_reg_` 등록 · `frgn_nreg_` 미등록으로 또 나뉩니다) |
| `orgn_` | 기관계 |
| `scrt_` 증권 · `ivtr_` 투신 · `bank_` 은행 · `insu_` 보험 · `fund_` 기금 · `mrbn_` 종금 · `pe_fund_` 사모 | 기관 세부 |
| `etc_corp_` 기타법인 · `etc_orgt_` 기타기관 | 그 밖 |

    _ntby_qty       순매수 수량   **천주**
    _ntby_tr_pbmn   순매수 금액   **백만원**

**단위 근거** — 2026-09-17 코스피 외국인 `-2632088` 을 백만원으로 읽으면
2.63조원 순매도입니다. 수량 `-17243` 을 천주로 읽으면 1,724만주이고,
둘을 나누면 주당 약 15.3만원으로 코스피 평균 단가와 어긋나지 않습니다.
**두 단위 모두 공식 문서에 적혀 있는 것은 보지 못했고, 위 대조로 판단했습니다.**

### 날짜 순서

KIS 는 **최근 → 과거** 순으로 줍니다. 추이선은 왼쪽이 과거여야 하므로
우리 API 가 **뒤집어서(과거 → 최근)** 돌려줍니다. 화면마다 뒤집으면
한 곳에서 빠뜨립니다.

---

## 4. 외국인 · 기관 순매수 상위

    경로   /uapi/domestic-stock/v1/quotations/foreign-institution-total
    tr_id  FHPTJ04400000

| 파라미터 | 넣는 값 |
|---|---|
| `FID_COND_MRKT_DIV_CODE` | `V` |
| `FID_COND_SCR_DIV_CODE` | `16449` |
| `FID_INPUT_ISCD` | `0000` 전체 · `0001` 코스피 · `1001` 코스닥 |
| `FID_DIV_CLS_CODE` | `0` 수량정렬 · `1` 금액정렬 |
| `FID_RANK_SORT_CLS_CODE` | `0` 순매수상위 · `1` 순매도상위 |
| `FID_ETC_CLS_CODE` | `0` 전체 · `1` 외국인 · `2` 기관계 · `3` 기타 |

이 값들은 **KIS 공식 저장소의 예제 코드**(`koreainvestment/open-trading-api`,
`examples_llm/domestic_stock/foreign_institution_total/`)에 적힌 그대로이고,
여섯 조합을 직접 불러 결과가 설명과 맞는 것을 확인했습니다.

### ⚠️ 확정치가 아닙니다 — 가집계입니다

KIS 공식 설명 그대로입니다.

> 증권사 직원이 장중에 집계/입력한 자료를 단순 누계한 수치로서,
> 입력시간은 외국인 09:30, 11:20, 13:20, 14:30 / 기관종합 10:00, 11:20,
> 13:20, 14:30 이며, 입력한 시간은 ±10분정도 차이가 발생할 수 있으며,
> 장운영 사정에 따라 변동될 수 있습니다.

**하루에 네 번만 바뀝니다.** 그래서 우리 캐시를 짧게 둘 이유가 없고,
**화면에는 「가집계」 임을 적어야 합니다.** 응답의 `meta.provisional` 이
`true` 로 오고 `meta.note` 에 위 시각이 들어 있습니다.

`inquire-investor`(종목별, `FHKST01010900`)로 받는 값은 확정치이지만
**종목 하나씩만** 물을 수 있어 상위 목록을 만들 수 없습니다.

### `ntby_qty` 가 무엇인지는 `FID_ETC_CLS_CODE` 가 정합니다

`ntby_qty` 는 **그 줄을 세운 기준값**입니다.

    ETC=1(외국인) → ntby_qty 가 frgn_ntby_qty 와 같다
    ETC=2(기관계) → ntby_qty 가 orgn_ntby_qty 와 같다

우리 API 는 헷갈리지 않게 `net` · `foreign` · `inst` 셋으로 나눠 보냅니다.

### 실측 (2026-09-17 마감 뒤 · 수량정렬 순매수)

    외국인  010140 삼성중공업 1,852,000 | 088350 한화생명 539,000 | 200470 에이팩트 533,000
    기관계  192650 드림텍 311,000 | 010140 삼성중공업 227,000 | 082740 한화엔진 218,000
    외국인 순매도  005935 삼성전자우 -758,000 | 005930 삼성전자 -718,000

### 주요 필드

| 필드 | 뜻 | 단위 |
|---|---|---|
| `mksc_shrn_iscd` · `hts_kor_isnm` | 종목코드 · 종목명 | |
| `stck_prpr` · `prdy_vrss` · `prdy_ctrt` | 현재가 · 전일대비 · 등락률 | |
| `ntby_qty` | 정렬 기준 순매수 수량 | 주 |
| `frgn_ntby_qty` · `frgn_ntby_tr_pbmn` | 외국인 순매수 | 주 · 백만원 |
| `orgn_ntby_qty` · `orgn_ntby_tr_pbmn` | 기관계 순매수 | 주 · 백만원 |
| `ivtr_` 투신 · `bank_` 은행 · `insu_` 보험 · `fund_` 기금 · `mrbn_` 종금 | 기관 세부 | |

---


> **KIS 밖의 출처는 `sector-sources.md` 에 있다** (2026-09-18).
> 네이버 비공식 주소로 업종 79개 · 테마 264개와 **그 구성종목**까지 받을 수 있다.
> KIS 38개와는 **기준이 다르다** — 거래소 표준 분류와 네이버 자체 분류라,
> 한쪽이 죽었을 때 갈아끼우면 화면의 항목 수와 이름이 통째로 바뀐다.
> 이중화가 아니라 **두 가지 보기**로 쓴다.

## 5. 테마 — KIS 에는 **없습니다**

**KIS Developers 국내주식 REST 에 테마 API 가 없습니다.**

근거는 KIS 공식 저장소(`koreainvestment/open-trading-api`)의
`examples_llm/domestic_stock/` 폴더입니다. 국내주식 엔드포인트가 전부
한 폴더씩 들어 있는데, 이름에 `theme` 이 들어간 것이 **하나도 없습니다.**
업종(`inquire_index_category_price`)·순위·투자자는 전부 있습니다.

비슷해 보이지만 테마가 아닌 것:

| | 무엇인가 | 왜 안 되나 |
|---|---|---|
| `psearch_title` · `psearch_result` | HTS 에 저장해 둔 **조건검색식** 불러오기 | 사람이 HTS 에서 만들어 두어야 한다. 테마 목록이 아니다 |
| `inquire_index_category_price` | 업종 | 테마와 다르다. 「우주항공」 「2차전지」 같은 묶음이 없다 |

### 붙일 곳이 있다면 — 네이버 (비공식)

    https://m.stock.naver.com/api/stocks/theme?page=1&pageSize=10

2026-09-17 에 불러보니 JSON 이 그대로 옵니다.

```json
{ "stockListSortType": "THEME",
  "groups": [
    { "no": 556, "name": "뉴로모픽 반도체", "totalCount": 7,
      "changeRate": "9.32", "riseCount": 7, "fallCount": 0, "steadyCount": 0 },
    { "no": 584, "name": "스페이스X(SpaceX)", "totalCount": 14,
      "changeRate": "9.16", "riseCount": 13, "fallCount": 0, "steadyCount": 1 }
  ] }
```

- `finance.naver.com/sise/theme.naver` 는 `302` 로 `stock.naver.com` 으로
  넘어갑니다. 위 JSON 주소를 써야 합니다
- **비공식입니다.** `server/dart.py` 가 시가총액 순위·지수 구성종목을 받을 때
  쓰는 것과 같은 계통(`m.stock.naver.com/api/...`)이라, 이미 이 저장소가
  쓰고 있는 방식이기는 합니다
- **아직 붙이지 않았습니다.** Cloudflare Worker 에서도 이 주소가 열리는지
  확인하지 못했습니다(엣지 IP 가 막힐 수 있습니다). 붙일지는 지시를 받고
  정합니다

`docs/data-sources.md` 의 「공식과 비공식을 갈라두는 이유」 를 따르면
테마는 **판단에 직결되는 값이 아니라 보조 정보**라 비공식으로 받아도
되는 쪽입니다.

---

## 6. 우리 API — 붙여 놓은 자리

브라우저는 `/api/kis/...` 로만 묻습니다. 로컬은 `server/kis_proxy.py`,
배포본은 `worker/kis-worker.js` 가 받습니다. **둘은 같은 응답을 냅니다** —
상수는 `holdings/tools/check-kis-consts.py` 가 대조합니다.

모두 `{ "ok": true, "data": …, "meta": {…} }` 모양입니다.

### `GET /api/kis/sectors`

    market=all(기본) | KOSPI | KOSDAQ

```json
{ "ok": true,
  "data": [ { "code": "0015", "name": "운송장비·부품", "market": "KOSPI",
              "price": 4710.23, "amt": 110.4, "pct": 2.4,
              "volume": 9163, "value": 1275558,
              "volShare": 4.15, "valueShare": null, "source": "KIS" } ],
  "meta": { "count": 41, "markets": ["KOSPI","KOSDAQ"],
            "volumeUnit": "천주", "valueUnit": "백만원", "cacheTtl": 60 } }
```

- `valueShare` 는 KIS 가 빈 값을 주므로 `null` 입니다 (위 1절)
- 시장 하나당 KIS 호출 한 번, `all` 이면 두 번

### `GET /api/kis/movers`

    dir=up(기본) | down
    market=all(기본) | KOSPI | KOSDAQ
    limit=1~30 (기본 30)

```json
{ "ok": true,
  "data": [ { "code": "042370", "name": "비츠로테크", "rank": 1,
              "price": 11440, "amt": 2640, "pct": 30.0,
              "volume": 8927607, "high": 11440, "low": 9060, "source": "KIS" } ],
  "meta": { "count": 30, "dir": "up", "market": "all", "max": 30, "cacheTtl": 30 } }
```

### `GET /api/kis/investor-flow`

    market=KOSPI(기본) | KOSDAQ
    days=1~300 (기본 30)

```json
{ "ok": true,
  "data": [ { "date": "2026-09-17", "index": 6715.41,
              "indexAmt": -2.56, "indexPct": -0.04,
              "retail":  { "qty": 7881,   "amt": 676052 },
              "foreign": { "qty": -17243, "amt": -2632088 },
              "inst":    { "qty": 5306,   "amt": 249709 }, "source": "KIS" } ],
  "meta": { "count": 30, "market": "KOSPI", "days": 30,
            "order": "과거→최근", "qtyUnit": "천주", "amtUnit": "백만원",
            "cacheTtl": 600 } }
```

- **`data` 는 과거 → 최근 순입니다.** 그대로 그리면 됩니다
- 며칠을 달라고 하든 KIS 호출은 **한 번**입니다

### `GET /api/kis/investor-top`

    dir=buy(기본) | sell
    by=qty(기본) | amt
    market=all(기본) | KOSPI | KOSDAQ
    limit=1~30 (기본 10)

```json
{ "ok": true,
  "data": {
    "foreign": [ { "code": "010140", "name": "삼성중공업",
                   "price": 21550, "amt": 1350, "pct": 6.68, "volume": 4575584,
                   "net":     { "qty": 1852000, "amt": 39911 },
                   "foreign": { "qty": 1852000, "amt": 39911 },
                   "inst":    { "qty": 227000,  "amt": 4892 }, "source": "KIS" } ],
    "inst":    [ { "code": "192650", "name": "드림텍", "…": "…" } ] },
  "meta": { "dir": "buy", "by": "qty", "market": "all",
            "qtyUnit": "주", "amtUnit": "백만원",
            "provisional": true,
            "note": "증권사 집계 가집계치 — 외국인 09:30·11:20·13:20·14:30, 기관 10:00·11:20·13:20·14:30 에 갱신 (±10분)",
            "cacheTtl": 120 } }
```

- **`meta.provisional` 이 `true` 면 화면에 「가집계」 라고 적습니다.**
  확정치인 줄 알고 보면 마감 뒤 숫자가 달라져 있어 「값이 틀렸다」 로 읽힙니다
- 한 번 부르면 KIS 호출 **두 번**입니다 (외국인 · 기관계)

### 호출량

캐시가 다 비었을 때 네 칸을 한 번씩 그리면 KIS 호출 **여섯 번**입니다
(업종 2 + 순위 1 + 추이 1 + 상위 2). 캐시 수명은 각각 60 · 30 · 600 · 120초입니다.

---

## 7. 확인하지 못한 것

**추측으로 채우지 않고 그대로 남깁니다.**

| 무엇 | 왜 |
|---|---|
| 업종 `0022` · `0023` 이 왜 비었나 | 응답에 안 옵니다. KRX 개편 흔적으로 보이지만 근거를 찾지 못했습니다 |
| `acml_tr_pbmn_rlim` 이 늘 빈 값인 이유 | 41행 전부 `""`. 장중에도 그런지 재보지 못했습니다 |
| 수량 단위(천주)의 공식 근거 | 금액과 나눠 대조해 판단했습니다. 문서에 적힌 것은 못 찾았습니다 |
| `FID_INPUT_ISCD` 로 시장을 거를 때 정말 그 시장만 오나 | 코스피(`0001`)로 걸렀는데 코스닥 종목처럼 보이는 것이 섞여 있었습니다. 종목별 소속을 따로 확인하지 못해 단정하지 않습니다. **기본값은 전체(`0000`)로 두었습니다** |
| 네이버 테마 JSON 을 Cloudflare Worker 에서도 받을 수 있나 | 로컬에서만 확인했습니다 |
| 장중 동작 | **전부 장 마감 뒤(한국시각 저녁)에 확인했습니다.** 장중 값의 갱신 주기는 재보지 못했습니다 |

---

## 8. 다시 확인하려면

`holdings/secrets.json` 이 있는 상태에서 `holdings/` 안에서 돌립니다.
**토큰은 1분에 한 번만 발급되므로 `get_token` 을 먼저 한 번 부르고 재사용합니다.**

```python
import sys; sys.path.insert(0, "server")
import kis_proxy as K
cfg = K.load_secrets(); K.get_token(cfg)

print(K.fetch_sectors(cfg)[0][:3])
print(K.fetch_movers(cfg, "up", "all", 3))
print(K.fetch_investor_flow(cfg, "KOSPI", 3))
print(K.fetch_investor_top(cfg, "buy", "all", "qty", 3)[0]["foreign"][:2])
```

서버째로 보려면 `holdings/preview.bat`(포트 8765) 을 띄우고
`http://localhost:8765/api/kis/sectors` 를 엽니다.
