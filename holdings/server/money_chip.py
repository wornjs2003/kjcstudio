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
    값 칸   chip_rules 「돈몰림」(winMin · mult · minEok · buyShare · holdMin) 한 곳
    한계    섹터 수급 판은 15:30 까지(11-26 · 그 전 14:00) · 지난 날 14:00 뒤 칸은 5분봉 어림이라 매수 몫 대신 등락 오름
    지난 판  past_spans — 그날 섹터 수급 판을 5분 칸마다 앞으로 가며 같은 셈(다수결 그대로)으로 붙음 · 빠짐 · 칸 시각은 그 칸이 끝나는 때
            (재권님 「지난 섹터 테마를 바탕으로 돈몰림 11월 2일부터 지금까지 적용해줘」 11-25 21:33 → 안에 「5분에 끝나면 그시간에 되야」 · 「진행해」 21:4x)
            묶음에 든 종목은 지금 목록(그날 목록은 안 남음 — 어림)
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


def past_spans(proxy, day, codes, open_at=None):
    """그날 5분 칸마다 붙음 · 빠짐 — → ({code: {"subs": [「업종 이름」 …], "spans": [[「HH:MM」 붙음, 「HH:MM」 빠짐 | None] …]}}, 못 읽은 까닭 | None).
    칸마다 그 칸까지 값만 보고 hits 와 같은 셈(group_vote · 다수결) · 칸 시각 = 그 칸이 끝나는 때(sector_flow.SLOT_TO — 장중에 그 칸 값을 처음 보는 때).
    한 종목이 든 묶음 중 하나라도 붙어 있으면 붙음 · 셈 못 한 칸(None)은 앞 상태 그대로.
    open_at 「HH:MM」 — 장중 셈은 여는 시각 전엔 돈몰림을 안 셈(dt30.chips_now 의 pre) · 그래서 그 앞 칸 시각은 여는 시각으로 모은다(마지막 프리장 칸 셈이 여는 때 상태 · qa 덧 11-25)."""
    import sector_flow
    w, h, mult = _win(), _hold(), chip_rules.get(CHIP, "mult")
    min_eok, share = chip_rules.get(CHIP, "minEok"), chip_rules.get(CHIP, "buyShare")
    tm = lambda s: "%s:%s" % (sector_flow.SLOT_TO[s][:2], sector_flow.SLOT_TO[s][2:])
    mem, why = {}, []
    for by, ko in BYS:
        try:
            data, _meta = sector_flow.board(proxy, by, day)
        except Exception as e:
            why.append("%s %s" % (ko, type(e).__name__))
            continue
        slots = data.get("slots") or []
        seqs = {}
        for r in data.get("rows") or []:
            amt, seq = r.get("amt") or {}, []
            for j, s in enumerate(slots):
                if amt.get(s) is None:
                    continue
                keep = set(slots[:j + 1])
                seq.append((max(tm(s), open_at) if open_at else tm(s), group_vote(dict(r, amt={x: v for x, v in amt.items() if x in keep}), slots, w, h, mult, min_eok, share)))
            if any(v is True for _, v in seq):
                seqs[r["name"]] = seq
        if not seqs:
            continue
        for name, cs in sector_flow._groups(proxy, by, list(codes)).items():
            if name in seqs:
                for c in cs:
                    mem.setdefault(c, []).append(("%s %s" % (ko, name), seqs[name]))
    out = {}
    for c, gs in mem.items():
        st, ev = {}, {}
        for g, seq in gs:
            for t, v in seq:
                ev.setdefault(t, []).append((g, v))
        spans, on = [], False
        for t in sorted(ev):
            for g, v in ev[t]:
                if v is not None:
                    st[g] = v
            now = any(st.values())
            if now and not on:
                spans.append([t, None])
            elif on and not now:
                spans[-1][1] = t
            on = now
        if spans:
            out[c] = {"subs": [g for g, seq in gs if any(v is True for _t, v in seq)], "spans": spans}
    return out, ("; ".join(why) if why else None)
