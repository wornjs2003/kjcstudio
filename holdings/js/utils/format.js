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
