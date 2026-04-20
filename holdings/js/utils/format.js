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
