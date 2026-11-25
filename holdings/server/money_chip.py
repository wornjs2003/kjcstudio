# -*- coding: utf-8 -*-
"""단타 칩 「돈몰림」 — 돈이 몰리는 업종 · 테마 묶음의 종목 (2026-11-25).

재권님(시황분석1 창) — 「돈이 몰리는 섹터나 테마에 속한 종목들 단타에 칩하나 · 어떤룰로 할지는 더 개선할거니 먼저 추가」 →
「30분이면 너무 늦을거같아」 → 「그 섹터의 전일대비 현재시각대금 비율로」 → (가)에 「응 시간과 배수는 ()로 빼서 내가 조절하게 해서 만들어줘」 ·
「처음부터 셈이되도록 켜줘」 → 개발2 창 「응 해」(14:35).

    값      섹터 수급 판(sector_flow.board · 업종 · 테마 5분 칸) — 이 파일은 새로 받지 않는다(그 판이 받은 것을 읽기만)
    셈      묶음마다 거래대금이 있는 마지막 칸까지 최근 winMin 분(칸 winMin/5 개)
              ① 그 칸들 거래대금 합 ≥ 전날 같은 칸들 합 × mult
              ② 그 합 ≥ minEok 억
              ③ 칸마다 매수 · 매도가 다 있으면 매수 ÷ (매수 + 매도) ≥ buyShare % · 하나라도 없으면(프리장 칸) 그 사이 묶음 등락이 오름
            다수결 — 위 셋을 최근 holdMin 분(5분 칸)마다 셈해 맞은 칸이 안 맞은 칸보다 많으면 붙어 있음(깜빡임 줄임 · 재권님 11-25 15:0x)
            칸 값이 하나라도 빠졌으면(사진 빠짐 · 전날 없음) 그 묶음은 안 셈 — 0 으로 꾸미지 않는다
    칩      맞은 묶음에 든 종목(감시 목록 · 시가총액 문턱은 부르는 쪽 chips_now 가 거름) · 하위 = 「업종 <이름>」 · 「테마 <이름>」
    값 칸   chip_rules 「돈몰림」(winMin · mult · minEok · buyShare) 한 곳
    한계    섹터 수급 판은 14:00 까지라 그 뒤는 13:55 칸 셈이 그대로 남는다 · 다시 지은 지난 판에는 아직 안 붙는다
"""
import chip_rules

CHIP = "돈몰림"
BYS = (("sector", "업종"), ("theme", "테마"))


def _win():
    return max(1, int(chip_rules.get(CHIP, "winMin")) // 5)


def group_hit(row, slots, w, mult, min_eok, share):
    """한 묶음 줄이 지금 맞나 — (맞음, 까닭) · 셈 못 하면 (None, 까닭)."""
    amt, prev = row.get("amt") or {}, row.get("prev") or {}
    have = [i for i, s in enumerate(slots) if amt.get(s) is not None]
    if not have:
        return None, "칸 없음"
    k = have[-1]
    if k - w + 1 < 0:
        return None, "칸 모자람"
    win = slots[k - w + 1:k + 1]
    cur, old = [amt.get(s) for s in win], [prev.get(s) for s in win]
    if any(v is None for v in cur + old):
        return None, "칸 빠짐"
    cs, ps = sum(cur), sum(old)
    if ps <= 0:
        return None, "전날 대금 없음"
    if cs < ps * mult or cs < min_eok:
        return False, "대금"
    buy, sell = row.get("buy") or {}, row.get("sell") or {}
    bs = [(buy.get(s), sell.get(s)) for s in win]
    if all(b is not None and v is not None for b, v in bs):
        tb, ts = sum(b for b, _ in bs), sum(v for _, v in bs)
        return (tb + ts > 0 and tb / (tb + ts) * 100 >= share), "매수 몫"
    pct = row.get("pct") or {}
    p1 = pct.get(slots[k])
    p0 = pct.get(slots[k - w]) if k - w >= 0 else pct.get(win[0])
    if p1 is None or p0 is None:
        return None, "등락 없음"
    return p1 > p0, "등락 오름"


_memo = {"key": None, "val": None}


def _hold():
    return max(1, int(chip_rules.get(CHIP, "holdMin")) // 5)


def group_vote(row, slots, w, h, mult, min_eok, share):
    """다수결 — 거래대금이 있는 마지막 칸까지 최근 h 칸마다 group_hit 를 셈 · 맞은 칸 > 안 맞은 칸이면 True · 셈 못 한 칸(None)은 어느 쪽에도 안 셈."""
    amt = row.get("amt") or {}
    have = [i for i, s in enumerate(slots) if amt.get(s) is not None]
    if not have:
        return None
    k = have[-1]
    ins = outs = 0
    for j in range(max(0, k - h + 1), k + 1):
        cut = dict(row, amt={s: v for s, v in amt.items() if s in slots and slots.index(s) <= j})
        r, _ = group_hit(cut, slots, w, mult, min_eok, share)
        if r is True:
            ins += 1
        elif r is False:
            outs += 1
    if not ins and not outs:
        return None
    return ins > outs


def hits(proxy, codes):
    """→ ({code: [하위 「업종 이름」 …]}, 못 읽은 까닭 | None) — codes 는 볼 종목(감시 목록).
    섹터 수급 판 셈이 무거워(그날 판 한 번 20초 넘게 · 11-25 잼) 사진이 새로 찍혔거나 룰 값 · 종목이 바뀔 때만 다시 셈 — 사진은 5분마다."""
    import sector_flow
    w, h, mult = _win(), _hold(), chip_rules.get(CHIP, "mult")
    min_eok, share = chip_rules.get(CHIP, "minEok"), chip_rules.get(CHIP, "buyShare")
    st = sector_flow.status() if hasattr(sector_flow, "status") else {}
    key = (st.get("lastSnap"), st.get("lastSnapAt"), st.get("frozenDay"), w, h, mult, min_eok, share, len(codes))
    if key[0] and _memo["key"] == key:
        return _memo["val"]
    out, why = {}, []
    for by, ko in BYS:
        try:
            data, _meta = sector_flow.board(proxy, by)
        except Exception as e:
            why.append("%s %s" % (ko, type(e).__name__))
            continue
        slots = data.get("slots") or []
        on = {r["name"] for r in data.get("rows") or [] if group_vote(r, slots, w, h, mult, min_eok, share) is True}
        if not on:
            continue
        for name, cs in sector_flow._groups(proxy, by, list(codes)).items():
            if name in on:
                for c in cs:
                    out.setdefault(c, []).append("%s %s" % (ko, name))
    val = (out, ("; ".join(why) if why else None))
    if not why:
        _memo.update(key=key, val=val)
    return val
