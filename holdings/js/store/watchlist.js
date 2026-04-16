/* 관심종목 localStorage 스토어 */

const KEY = 'kh:watchlist:v1';

export function loadWatchlist() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (_) {
    return [];
  }
}

export function saveWatchlist(codes) {
  try {
    localStorage.setItem(KEY, JSON.stringify(codes));
  } catch (_) { /* 무시 */ }
}

export function addCode(code) {
  const list = loadWatchlist();
  if (!list.includes(code)) {
    list.push(code);
    saveWatchlist(list);
  }
  return list;
}

export function removeCode(code) {
  const list = loadWatchlist().filter(c => c !== code);
  saveWatchlist(list);
  return list;
}
