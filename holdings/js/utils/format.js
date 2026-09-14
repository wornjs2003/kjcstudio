/* 숫자·통화·거래량 포맷 */

export function fmtPrice(n) {
  if (n == null || Number.isNaN(n)) return '—';
  return n.toLocaleString('ko-KR');
}

export function fmtChange(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const sign = n > 0 ? '+' : (n < 0 ? '' : '');
  return `${sign}${n.toLocaleString('ko-KR')}`;
}

export function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

export function fmtVolume(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (n >= 10_000)      return `${(n / 10_000).toFixed(1)}만`;
  return n.toLocaleString('ko-KR');
}

export function changeDirection(n) {
  if (n > 0) return 'up';
  if (n < 0) return 'down';
  return 'flat';
}

/* 금액 포맷 — 입력은 백만원 단위
   예) 1,234,567 (백만원) → "1조 2,345억" */
export function fmtMoneyM(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1_000_000) {
    const jo = Math.floor(abs / 1_000_000);
    const eok = Math.round((abs % 1_000_000) / 100);
    return `${sign}${jo}조 ${eok.toLocaleString('ko-KR')}억`;
  }
  if (abs >= 100) {
    const eok = (abs / 100);
    return `${sign}${eok.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}억`;
  }
  return `${sign}${abs.toLocaleString('ko-KR')}백만`;
}

/* 순매수용 금액 (부호 포함) — 입력 백만원 단위 */
export function fmtMoneyMSigned(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n === 0) return '0';
  const sign = n > 0 ? '+' : '-';
  return `${sign}${fmtMoneyM(Math.abs(n))}`;
}

/* 수량(주) 포맷 */
export function fmtShares(n) {
  if (n == null || Number.isNaN(n)) return '—';
  return `${n.toLocaleString('ko-KR')}주`;
}

/* 거래대금 (원 단위 입력) → "X조 Y억" / "Y억" / "Y만원" */
export function fmtKrw(won) {
  if (won == null || Number.isNaN(won)) return '—';
  const abs = Math.abs(won);
  const sign = won < 0 ? '-' : '';
  if (abs >= 1_000_000_000_000) {
    const jo = Math.floor(abs / 1_000_000_000_000);
    const eok = Math.round((abs % 1_000_000_000_000) / 100_000_000);
    return `${sign}${jo}조 ${eok.toLocaleString('ko-KR')}억`;
  }
  if (abs >= 100_000_000) {
    const eok = Math.round(abs / 100_000_000);
    return `${sign}${eok.toLocaleString('ko-KR')}억`;
  }
  if (abs >= 10_000) {
    const man = Math.round(abs / 10_000);
    return `${sign}${man.toLocaleString('ko-KR')}만원`;
  }
  return `${sign}${abs.toLocaleString('ko-KR')}원`;
}

/* ──────────────────────────────────────────────────────────────────────────
   토스식 표기 — 단위를 끝에 붙이고, 조 단위는 소수 한 자리까지
     fmtWon(262000)      → "262,000원"
     fmtMoneyKr(15317250)→ "1,531.7조원"   (입력 단위: 억원)
     fmtMoneyKr(2019)    → "2,019억원"
     dirClass(-1.2)      → "kh-down"
   ────────────────────────────────────────────────────────────────────────── */

export function fmtNum(v, digits = 0) {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('ko-KR', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
}

export function fmtWon(v) {
  return v == null ? '—' : fmtNum(v) + '원';
}

/* 입력 단위는 억원 (KIS 의 시가총액 hts_avls 가 억원 단위로 온다) */
export function fmtMoneyKr(eok) {
  if (eok == null) return '—';
  if (eok >= 10000) return fmtNum(eok / 10000, 1) + '조원';
  return fmtNum(Math.round(eok)) + '억원';
}

/* 주식 수 — 만 단위로 줄여 읽는다 */
export function fmtShareCount(n) {
  if (n == null) return '—';
  if (n >= 10000) return fmtNum(Math.round(n / 10000)) + '만주';
  return fmtNum(n) + '주';
}

/* 오를 때 빨강, 내릴 때 파랑 (한국식) */
export function dirClass(n) {
  if (n == null) return 'kh-mut';
  if (n === 0) return 'kh-flat';   // 보합 — 빨강도 파랑도 아니다
  return n > 0 ? 'kh-up' : 'kh-down';
}

/* 증감 표기 — "▲ 1,200원 (1.59%)" */
export function fmtDelta(amount, pct, unit = '원', digits = 0) {
  if (amount == null || pct == null) return '';
  const mark = amount >= 0 ? '▲' : '▼';
  return `${mark} ${fmtNum(Math.abs(amount), digits)}${unit} (${Math.abs(pct).toFixed(2)}%)`;
}

/* ──────────────────────────────────────────────────────────────────────────
   지금이 어느 장인가

   넥스트레이드(대체거래소)가 생기면서 08:00 부터 20:00 까지 거래가 이어집니다.
   정규장 밖에서는 종목 값은 움직이지만 **지수는 움직이지 않습니다.**
   지수가 0.00% 로 멈춰 있는 게 고장이 아니라는 걸 화면에 적어주기 위한 함수입니다.

   확인한 것 (2026-09-14)
     넥스트레이드 프리마켓 08:00~08:50 · 전체 운영 08:00~20:00
   판단 기준은 한국 시각(KST)이다. 보는 사람 PC 시계와 무관하다.

   확인하지 못한 것
     애프터마켓 시작 시각. 공식 페이지가 자바스크립트로 그려져 읽지 못했습니다.
     그래서 정규장이 끝난 뒤(15:30~20:00)를 뭉뚱그려 '애프터마켓' 으로 봅니다.
     공휴일도 가리지 못합니다.
   ────────────────────────────────────────────────────────────────────────── */

export function marketPhase(now = new Date()) {
  /* 한국 시각으로 고정한다. 보는 사람의 PC 시계가 무엇이든 같은 답이 나와야 한다.
     서버(kis_proxy.py)와 배포용 워커(kis-worker.js)도 KST 로 판단하므로,
     여기만 브라우저 로컬 시각을 쓰면 화면 문구와 실제 시세 기준이 어긋난다.
     실제로 PC 를 UTC 로 두고 돌려보면 한국 09:00~15:00 내내
     화면은 "장 마감", 서버는 정규장(J)으로 조회한다.
     보정 방식은 kis-worker.js 의 quoteMarketDiv 와 같게 맞췄다. */
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();                 // 0 일요일 · 6 토요일
  if (day === 0 || day === 6) {
    return { id: 'closed', label: '주말 · 장 마감', note: '다음 개장 월요일 09:00' };
  }

  const hm = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  if (hm >= 480 && hm < 530) {      // 08:00 ~ 08:50
    return { id: 'pre', label: '프리마켓', note: '넥스트레이드 · 08:50까지' };
  }
  if (hm >= 530 && hm < 540) {      // 08:50 ~ 09:00 — 프리마켓은 끝났고 정규장 전
    return { id: 'preclose', label: '개장 전', note: '09:00 개장' };
  }
  if (hm >= 540 && hm < 930) {      // 09:00 ~ 15:30
    return { id: 'regular', label: '장중', note: '15:30까지' };
  }
  if (hm >= 930 && hm < 1200) {     // 15:30 ~ 20:00
    return { id: 'after', label: '애프터마켓', note: '넥스트레이드 · 20:00까지' };
  }
  return { id: 'closed', label: '장 마감', note: '다음 개장 09:00' };
}

