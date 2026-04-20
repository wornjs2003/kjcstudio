#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KJC Studio · refresh-works.py
----------------------------------------------------------------
assets/images/works/<category>/ 폴더를 스캔해서 data/works.json 을 자동 갱신.

정책
- 발견된 이미지 파일 → 새 엔트리 추가 (메타데이터 자동 생성)
- 기존 엔트리 중 thumbnail 이 실재 파일이면 → 그대로 유지 (제목/연도 손수 편집한 값 보존)
- 기존 엔트리 중 thumbnail 이 빈 문자열(플레이스홀더) → 해당 카테고리에 실제 이미지가
  하나라도 발견되면 자동 제거, 없으면 보존 (처음 빈 상태에서 레이아웃 보여주기용)
- 기존 엔트리 중 thumbnail 이 존재하지 않는 파일을 가리킴 → 제거 (orphan)

파일명 규칙 (선택)
- `01_elf-warrior.jpg`          → order=1, 제목="Elf Warrior", span 자동
- `elf-warrior_tall.jpg`        → span="tall" 강제 (접미사로 명시)
- `02_엘프전사_wide.jpg`        → order=2, 제목="엘프전사", span="wide"
- 접미사 없으면 Pillow 로 이미지 크기 읽어 비율로 span 자동 결정
  (Pillow 없으면 "large" 기본값)

사용법
- 터미널: `python3 tools/refresh-works.py`
- Mac: 루트의 `refresh-works.command` 더블클릭
"""

from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

# ── 경로/상수 ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
IMG_ROOT = ROOT / "assets" / "images" / "works"
JSON_PATH = ROOT / "data" / "works.json"

CATEGORIES = ["3d-modeling", "ai-work", "web-interactive", "branding"]

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
SPAN_HINTS = {"tall", "wide", "square", "large"}

CATEGORY_PREFIX = {
    "3d-modeling":     "3dm",
    "ai-work":         "aiw",
    "web-interactive": "web",
    "branding":        "brd",
}

# ── 유틸 ─────────────────────────────────────────────────────
def try_pil_size(path: Path):
    """Pillow 있으면 (width, height) 리턴, 없거나 실패하면 None."""
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def span_from_ratio(w: int, h: int) -> str:
    if h <= 0:
        return "large"
    r = w / h
    if r < 0.75:
        return "tall"
    if r > 1.35:
        return "wide"
    if 0.92 <= r <= 1.08:
        return "square"
    return "large"


def span_from_filename(name: str):
    """파일명 접미사로 span 힌트 추출. `xxx_tall.jpg` 같은 형식."""
    stem = Path(name).stem.lower()
    for h in SPAN_HINTS:
        if stem.endswith(f"_{h}") or stem.endswith(f"-{h}"):
            return h
    return None


def strip_span_suffix(stem: str) -> str:
    low = stem.lower()
    for h in SPAN_HINTS:
        if low.endswith(f"_{h}"):
            return stem[: -(len(h) + 1)]
        if low.endswith(f"-{h}"):
            return stem[: -(len(h) + 1)]
    return stem


def order_from_filename(stem: str):
    m = re.match(r"^(\d+)", stem)
    if m:
        return int(m.group(1))
    return None


def strip_order_prefix(stem: str) -> str:
    return re.sub(r"^\d+[-_]+", "", stem)


def titleize(stem: str) -> str:
    s = strip_span_suffix(stem)
    s = strip_order_prefix(s)
    s = re.sub(r"[_-]+", " ", s).strip()
    if not s:
        return "Untitled"
    # 한글 포함이면 그대로, 영문이면 Title Case
    if re.search(r"[가-힣]", s):
        return s
    return s.title()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {
            "_comment": "작업물은 refresh-works.command 로 자동 갱신됩니다. 수동 편집 가능.",
            "works": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def scan_category(cat: str):
    cat_dir = IMG_ROOT / cat
    if not cat_dir.exists():
        return []
    files = [
        p for p in cat_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMG_EXTS and not p.name.startswith(".")
    ]
    # 파일명 순 정렬 (숫자 접두사가 있으면 자연스럽게 정렬)
    files.sort(key=lambda p: (order_from_filename(p.stem) or 10_000, p.name.lower()))
    return files


# ── 메인 ─────────────────────────────────────────────────────
def main() -> int:
    doc = load_json(JSON_PATH)
    existing = doc.get("works", [])
    by_thumb = {w.get("thumbnail"): w for w in existing if w.get("thumbnail")}
    placeholders = [w for w in existing if not w.get("thumbnail")]

    # 카테고리별 기존 max order 파악 → 새로 들어오는 것에 이어 번호 부여
    max_order = {c: 0 for c in CATEGORIES}
    for w in existing:
        c = w.get("category")
        if c in max_order:
            max_order[c] = max(max_order[c], int(w.get("order") or 0))

    kept_placeholders = []
    result_list = []
    added = 0
    kept = 0

    cat_has_real_image = {}

    for cat in CATEGORIES:
        files = scan_category(cat)
        cat_has_real_image[cat] = len(files) > 0

        for idx, img in enumerate(files, start=1):
            rel_path = f"assets/images/works/{cat}/{img.name}"

            if rel_path in by_thumb:
                result_list.append(by_thumb[rel_path])
                kept += 1
                continue

            stem = img.stem
            explicit_order = order_from_filename(stem)
            if explicit_order is not None:
                order_val = explicit_order
            else:
                max_order[cat] += 1
                order_val = max_order[cat]

            span = span_from_filename(img.name)
            if not span:
                size = try_pil_size(img)
                span = span_from_ratio(*size) if size else "large"

            prefix = CATEGORY_PREFIX.get(cat, cat[:3])
            title = titleize(stem)
            # id 는 경로 기반으로 안정적으로 생성
            clean_stem = strip_span_suffix(stem)
            clean_stem = re.sub(r"[^A-Za-z0-9가-힣]+", "-", clean_stem).strip("-").lower()
            if not clean_stem:
                clean_stem = f"img-{idx:03d}"
            entry_id = f"{prefix}-{clean_stem}"[:60]

            result_list.append({
                "id": entry_id,
                "category": cat,
                "title": title,
                "year": 2026,
                "thumbnail": rel_path,
                "span": span,
                "order": order_val,
            })
            added += 1

    # 플레이스홀더 처리: 해당 카테고리에 실제 이미지가 없으면 보존
    for ph in placeholders:
        c = ph.get("category")
        if c not in cat_has_real_image:
            kept_placeholders.append(ph)
        elif not cat_has_real_image[c]:
            kept_placeholders.append(ph)
        # else: 실제 이미지 생기면 플레이스홀더 제거

    # orphan 개수 집계 (thumbnail 이 실제 파일이 없는 기존 엔트리)
    orphan = 0
    for thumb, w in by_thumb.items():
        if (ROOT / thumb).exists():
            continue
        orphan += 1
        # 자동으로 result_list 에는 포함되지 않음 (파일 없으면 탐색 안 됨)

    # 카테고리 순서 + order 순서로 정렬
    cat_idx = {c: i for i, c in enumerate(CATEGORIES)}
    all_entries = kept_placeholders + result_list
    all_entries.sort(key=lambda w: (
        cat_idx.get(w.get("category"), 999),
        int(w.get("order") or 0),
        w.get("id") or "",
    ))

    doc["works"] = all_entries
    doc.setdefault(
        "_comment",
        "작업물은 refresh-works.command 로 자동 갱신됩니다. 수동 편집 가능."
    )

    save_json(JSON_PATH, doc)

    # 리포트
    print("")
    print("  ─────────────────────────────────────────")
    print("   KJC Studio · works.json 갱신 결과")
    print("  ─────────────────────────────────────────")
    print(f"   추가된 이미지        : {added}")
    print(f"   유지된 기존 항목     : {kept}")
    print(f"   orphan (파일 없음)   : {orphan}")
    print(f"   남은 플레이스홀더    : {len(kept_placeholders)}")
    print(f"   총 엔트리            : {len(all_entries)}")
    print("  ─────────────────────────────────────────")
    print("  카테고리별 상세:")
    for cat in CATEGORIES:
        files = scan_category(cat)
        entries_cat = [e for e in all_entries if e.get("category") == cat]
        with_thumb = [e for e in entries_cat if e.get("thumbnail")]
        print(f"    · {cat:18s}  이미지 {len(files)}장, 엔트리 {len(entries_cat)}개")
        for e in with_thumb[:5]:
            print(f"        - {e.get('title')}  ({e.get('span')})")
        if len(with_thumb) > 5:
            print(f"        … 외 {len(with_thumb) - 5}개")
    print("")
    print(f"   저장 경로 : {JSON_PATH}")
    print("")
    # Pillow 없을 때 안내
    try:
        import PIL  # type: ignore
        _ = PIL
    except Exception:
        print("  ℹ Pillow 미설치: 이미지 비율 자동 인식 비활성. 파일명 접미사(_tall/_wide/_square)로")
        print("    span 지정하거나 `pip3 install --break-system-packages Pillow` 로 설치하면 자동 인식.")
        print("")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("", file=sys.stderr)
        print(f"  ⚠ 갱신 실패: {e}", file=sys.stderr)
        sys.exit(1)
