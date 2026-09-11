/* ==========================================================================
   실데이터가 아닌 값은 화면에 내보내지 않는다

   주식 화면에서 목업 숫자가 실제 시세처럼 보이면 잘못된 판단으로 이어진다.
   그래서 값을 그리기 전에 반드시 이 헬퍼를 거쳐, 실제로 받아온 값일 때만
   숫자를 보여주고 아니면 로딩 표시나 대시를 내보낸다.

   판단 기준은 항목에 붙는 isLive 플래그다.
     - js/data/live.js 의 applyLiveToStock() 이 실데이터를 씌우면서 true 로 만든다
     - 지수는 서버가 내려주는 source === 'KIS' 로 구분한다
   ========================================================================== */

/* 아직 한 번도 불러오지 않은 상태인지 (첫 로드 중) */
let _initialLoad = true;
export function markLoaded() { _initialLoad = false; }
export function isInitialLoad() { return _initialLoad; }

const DASH = '—';
const LOADING = '불러오는 중';

/**
 * 실데이터일 때만 값을 보여준다.
 * @param {boolean} isLive  실제로 받아온 값인가
 * @param {*} value         보여줄 값 (이미 포맷된 문자열이거나 숫자)
 * @param {object} opts     loading: 첫 로드 중 문구, empty: 값 없을 때 문구
 */
export function liveOnly(isLive, value, opts = {}) {
  if (isLive && value != null && value !== '') return value;
  if (_initialLoad) return opts.loading ?? LOADING;
  return opts.empty ?? DASH;
}

/* 값이 비었을 때 붙일 클래스 (흐리게 표시) */
export function liveClass(isLive) {
  return isLive ? '' : 'kh-nodata';
}

/* 툴팁용 설명 — 왜 값이 없는지 알려준다 */
export function liveTitle(isLive) {
  if (isLive) return '';
  return _initialLoad
    ? '시세를 불러오는 중입니다'
    : '아직 실시간 시세가 연결되지 않은 항목입니다';
}
