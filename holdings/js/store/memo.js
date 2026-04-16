/* 종목별 메모 localStorage 스토어 */

const KEY = 'kh:memos:v1';

function loadAll() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (_) { return {}; }
}

function saveAll(all) {
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch (_) {}
}

export function getMemo(code) {
  return loadAll()[code] || '';
}

export function setMemo(code, text) {
  const all = loadAll();
  if (text && text.trim()) {
    all[code] = text;
  } else {
    delete all[code];
  }
  saveAll(all);
}
