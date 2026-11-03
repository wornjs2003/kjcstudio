/* 매매 비용 — 주식 회고(review.js)가 차익을 셀 때 빼는 세금 · 수수료의 율. **이 값은 여기 한 곳에만 둔다**
   (「같은 값은 한 곳에만 둔다」 · 2026-11-03 재권님 「거래세랑 증권사에서 내야하는 세금낸것도 표기해주고」 ·
   「수수료율 0.01로 해놔 코스피와 코스닥 매매시 세금이 다른거도 확인해」).

   SELL_TAX — 팔 때 판 금액에 붙는 세금, 시장마다. 2026-01-01 시행 증권거래세법 시행령(대통령령 제36001호 · 2025-12-31 공포):
     코스피  증권거래세 0.05% + 농어촌특별세 0.15% = 합 0.20%
     코스닥  증권거래세 0.20% (농어촌특별세 없음)
     합계는 같고 나뉨이 다르다. 코넥스(0.10%)는 회고 종목 고르기(코스피 200 · 코스닥 150 · 관심종목)에 없어 안 둔다.
     출처: 법제처 국가법령정보센터 시행령 개정 목록(시행일) · 한국세정신문 · 머니투데이 · 서울경제 보도(율) — 시행령 조문 원문은 못 열어 봄(2026-11-03 · 개발1)
     시장을 모르는 종목은 세금 · 수익금 · 수익률을 null 로 낸다 — 세금을 안 뺀 값을 수익금처럼 내지 않는다(못 쟀으면 0 이 아니라 「못 쟀다」 · 2026-11-03 개념정의 검수)
   BROKER_FEE_RATE — 증권사 매매 수수료(살 때 · 팔 때 각각 그 금액에). 0.01% — 재권님이 주신 율(2026-11-03 「수수료율 0.01로 해놔」) */
export const SELL_TAX = {
  KOSPI: [['거래세', 0.0005], ['농특세', 0.0015]],
  KOSDAQ: [['거래세', 0.002]],
};
export const BROKER_FEE_RATE = 0.0001;

/* 한 번의 매매(매수가 · 매도가 · 수량)를 센다. 셋 중 하나라도 비면 null.
   세금 · 수수료는 항목마다 원 미만을 버린다(증권사 계산서 관례 — 증권사마다 다를 수 있음) */
export function legCost(buy, sell, qty, market) {
  if (![buy, sell, qty].every((x) => Number.isFinite(x) && x > 0)) return null;
  const buyAmt = buy * qty, sellAmt = sell * qty;
  const rates = SELL_TAX[market];
  const taxes = rates ? rates.map(([name, r]) => [name, Math.floor(sellAmt * r)]) : null;
  const tax = taxes ? taxes.reduce((a, [, v]) => a + v, 0) : null;
  const fee = BROKER_FEE_RATE == null ? null : Math.floor(buyAmt * BROKER_FEE_RATE) + Math.floor(sellAmt * BROKER_FEE_RATE);
  const gross = sellAmt - buyAmt;
  const net = tax == null || fee == null ? null : gross - tax - fee;
  return { buyAmt, sellAmt, gross, taxes, tax, fee, net, pct: net == null ? null : (net / buyAmt) * 100 };
}

/* 여러 번의 매매를 합친다 — 수익률은 산 금액 합계에 대한 순차익 · 한 줄이라도 못 셌으면 순차익 · 수익률은 null */
export function sumCosts(legs) {
  const ok = legs.filter(Boolean);
  if (!ok.length) return null;
  const s = (k) => ok.reduce((a, x) => a + x[k], 0);
  const buyAmt = s('buyAmt'), net = ok.some((x) => x.net == null) ? null : s('net');
  const taxes = ok.some((x) => !x.taxes) ? null
    : ok[0].taxes.map(([name], i) => [name, ok.reduce((a, x) => a + x.taxes[i][1], 0)]);
  return { buyAmt, sellAmt: s('sellAmt'), gross: s('gross'), taxes, tax: taxes ? s('tax') : null,
    fee: ok.some((x) => x.fee == null) ? null : s('fee'), net, pct: net == null ? null : (net / buyAmt) * 100 };
}
