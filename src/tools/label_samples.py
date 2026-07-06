#!/usr/bin/env python3
"""TFT Vision — 수동 데이터 레이블링 CLI 도구 (다중 폴더 + 한글 입력 지원).

ROI 유형에 따라 세 가지 모드로 동작:
  - champion 모드 (shop_card, shop_slot_*): 챔피언 이름만 입력 (한글 가능)
  - structured 모드 (board/bench): 기물 목록을 champ_starLevel 형식으로 입력
  - simple 모드 (기타 ROI): 자유 텍스트 레이블

여러 폴더를 동시에 지정하거나 --shop 옵션으로 5개 상점 슬롯을
하나의 shop_card 데이터셋으로 통합 라벨링할 수 있습니다.

사용법:
    # 단일 폴더 (기존 방식)
    python -m src.tools.label_samples samples/xxx/shop_slot_1 --roi shop_slot_1

    # 상점 5개 슬롯 통합 라벨링
    python -m src.tools.label_samples samples/session_xxx --shop

    # 여러 폴더 명시적 지정
    python -m src.tools.label_samples \
        samples/xxx/shop_slot_1 samples/xxx/shop_slot_2 \
        samples/xxx/shop_slot_3 samples/xxx/shop_slot_4 \
        samples/xxx/shop_slot_5 --roi shop_card

    # 보드/벤치 라벨링 (구조화 모드)
    python -m src.tools.label_samples samples/xxx/my_board --roi my_board
"""

import argparse
import csv
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("tft-vision.label_samples")

CSV_FIELDS = [
    "image_path",
    "roi",
    "slot",
    "champion",
    "star_level",
    "items",
    "position",
    "label_raw",
    "label_normalized",
    "notes",
    "created_at",
]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

# ── 챔피언명 정규화 ────────────────────────────────────────────

_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "champion_aliases.json"

SPECIAL_MAP: dict[str, str] = {
    "모름": "unknown",
    "잘못됨": "bad",
}


def _load_aliases() -> dict[str, str]:
    if not _ALIASES_PATH.exists():
        logger.warning("champion_aliases.json 없음 — 정규화 없이 원본 저장")
        return {}
    try:
        with open(_ALIASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("aliases", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("champion_aliases.json 로드 실패: %s", e)
        return {}


def normalize_champion_name(korean_name: str, aliases: dict[str, str]) -> str:
    k = korean_name.strip()
    if not k:
        return k
    if k in SPECIAL_MAP:
        return SPECIAL_MAP[k]
    if k in aliases:
        return aliases[k]
    return k


# ── 라벨 정규화 ────────────────────────────────────────────────


def normalize_label_text(raw: str, mode: str, aliases: dict[str, str]) -> dict:
    text = raw.strip()
    if not text:
        return {"champion": "", "star_level": "", "label_normalized": ""}

    if mode == "simple":
        return {"champion": "", "star_level": "", "label_normalized": text}

    if mode == "champion":
        norm = normalize_champion_name(text, aliases)
        return {"champion": norm, "star_level": "", "label_normalized": norm}

    if mode == "structured":
        if text in SPECIAL_MAP.values() or text in SPECIAL_MAP:
            norm = normalize_champion_name(text, aliases)
            return {"champion": norm, "star_level": "", "label_normalized": norm}

        units = [u.strip() for u in text.split(",") if u.strip()]
        champs: list[str] = []
        stars: list[str] = []
        norm_units: list[str] = []

        for unit in units:
            if "_" in unit:
                champ_part, _, star_part = unit.rpartition("_")
                if star_part in ("1", "2", "3", "unknown"):
                    nc = normalize_champion_name(champ_part, aliases)
                    champs.append(nc)
                    stars.append(star_part)
                    norm_units.append(f"{nc}_{star_part}")
                else:
                    nc = normalize_champion_name(unit, aliases)
                    champs.append(nc)
                    stars.append("unknown")
                    norm_units.append(nc)
            else:
                nc = normalize_champion_name(unit, aliases)
                champs.append(nc)
                stars.append("unknown")
                norm_units.append(nc)

        return {
            "champion": ",".join(champs),
            "star_level": ",".join(stars),
            "label_normalized": ",".join(norm_units),
        }

    return {"champion": "", "star_level": "", "label_normalized": text}


# ── ROI 모드 분류 ──────────────────────────────────────────────

# shop_card는 champion 모드로 취급 (shop_slot_N과 동일)
STRUCTURED_ROIS = {"my_board", "my_bench", "enemy_board", "enemy_bench"}
CHAMPION_ROIS = {"shop_card"}


def _is_champion_roi(roi: str) -> bool:
    return roi.startswith("shop_slot") or roi in CHAMPION_ROIS


def get_mode_name(roi: str) -> str:
    if _is_champion_roi(roi):
        return "champion"
    if roi in STRUCTURED_ROIS:
        return "structured"
    return "simple"


# ── 폴더/슬롯 해석 ─────────────────────────────────────────────

SHOP_SLOT_RE = re.compile(r"shop_slot_(\d+)$", re.IGNORECASE)


def detect_slot(dir_path: Path) -> str:
    """디렉토리명에서 slot 번호 추출. (shop_slot_1 → '1')"""
    m = SHOP_SLOT_RE.search(dir_path.name)
    if m:
        return str(int(m.group(1)))
    return ""


def collect_images(dirs: list[Path], roi: str) -> list[dict]:
    """여러 디렉토리에서 이미지 수집.
    
    Returns:
        [{path, roi, slot, image_path}, ...]
    """
    items: list[dict] = []
    for d in dirs:
        if not d.is_dir():
            logger.warning("디렉토리 없음: %s", d)
            continue
        slot = detect_slot(d)
        images = sorted(p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        for img in images:
            # image_path: shop_slot_1/filename.png 형태
            rel = f"{d.name}/{img.name}"
            items.append({
                "path": img,
                "roi": roi,
                "slot": slot,
                "image_path": rel,
            })
    return items


def find_shop_dirs(session_dir: Path) -> list[Path]:
    """session_dir 아래 shop_slot_1~5 폴더 찾기."""
    dirs = []
    for i in range(1, 6):
        d = session_dir / f"shop_slot_{i}"
        if d.is_dir():
            dirs.append(d)
    return dirs


# ── CSV I/O ────────────────────────────────────────────────────


def load_existing_labels(csv_path: Path) -> dict[str, dict]:
    """기존 labels.csv 로드 → {image_path: row_dict}.

    구 포맷 자동 마이그레이션 (label → label_raw/label_normalized, slot 추가).
    """
    labels: dict[str, dict] = {}
    if not csv_path.exists():
        return labels

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_fields = reader.fieldnames or []
        rows = list(reader)

    if not rows:
        return labels

    needs_migration = not set(CSV_FIELDS).issubset(existing_fields)

    for row in rows:
        if needs_migration:
            new_row = {}
            for field in CSV_FIELDS:
                val = row.get(field, "")
                if field == "label_raw":
                    lv = row.get("label", "")
                    new_row["label_raw"] = lv if lv else val
                elif field == "label_normalized":
                    lv = row.get("label", "")
                    new_row["label_normalized"] = lv if lv else val
                elif field == "slot":
                    new_row["slot"] = row.get("slot", "")
                else:
                    new_row[field] = val
            labels[row["image_path"]] = new_row
        else:
            labels[row["image_path"]] = dict(row)

    if needs_migration:
        logger.info(
            "CSV 마이그레이션: %d개 row → %d 컬럼",
            len(rows), len(CSV_FIELDS),
        )
        write_all_rows(csv_path, list(labels.values()))

    return labels


def write_all_rows(csv_path: Path, rows: list[dict]):
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            writer.writerow(out)


# ── 이미지 유틸 ────────────────────────────────────────────────


def try_show_image(image_path: Path, roi: str, index: int, total: int) -> bool:
    try:
        import cv2
        img = cv2.imread(str(image_path))
        if img is not None:
            h, w = img.shape[:2]
            if max(w, h) > 800:
                scale = 800.0 / max(w, h)
                display = cv2.resize(img, (int(w * scale), int(h * scale)))
            else:
                display = img.copy()
            cv2.imshow(f"Label: {roi} ({index}/{total})", display)
            cv2.waitKey(1)
            return True
    except Exception:
        pass
    return False


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


# ── 프롬프트 ───────────────────────────────────────────────────


def show_existing_info(row: dict | None) -> str:
    if not row:
        return ""
    parts = []
    slot = row.get("slot", "").strip()
    champ = row.get("champion", "").strip()
    star = row.get("star_level", "").strip()
    raw = row.get("label_raw", "").strip()
    norm = row.get("label_normalized", "").strip()
    if slot:
        parts.append(f"slot={slot}")
    if champ and star:
        parts.append(f"champion='{champ}' star='{star}'")
    elif champ:
        parts.append(f"champion='{champ}'")
    elif raw:
        parts.append(f"입력='{raw}'")
    if norm and norm != raw:
        parts.append(f"정규화='{norm}'")
    if row.get("notes", "").strip():
        parts.append(f"notes='{row['notes'].strip()}'")
    return f"  기존: {' | '.join(parts)}" if parts else ""


def prompt_champion(existing_row: dict | None) -> dict | None:
    info = show_existing_info(existing_row)
    if info:
        print(info)
    print("  챔피언 이름 (한글/영문) | 모름 | 잘못됨 | Enter=skip")
    inp = input("  [champion] (q=quit, qq=immediate): ").strip()
    if not inp:
        return None
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}
    return {"label_raw": inp}


def prompt_structured(existing_row: dict | None) -> dict | None:
    info = show_existing_info(existing_row)
    if info:
        print(info)
    print("  형식: 이름_별개수,이름_별개수,... (예: 아리_2,야스오_1)")
    print("  star: 1|2|3|unknown  |  모름 | 잘못됨  |  Enter=skip")
    inp = input("  [units] (q=quit, qq=immediate): ").strip()
    if not inp:
        return None
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}
    notes = input("  [notes] (Enter=none): ").strip()
    return {"label_raw": inp, "notes": notes}


def prompt_simple(existing_row: dict | None) -> dict | None:
    info = show_existing_info(existing_row)
    if info:
        print(info)
    inp = input("  [label] (Enter=skip, q=quit, qq=immediate): ").strip()
    if not inp:
        return None
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}
    return {"label_raw": inp}


PROMPT_DISPATCH = {
    "champion": prompt_champion,
    "structured": prompt_structured,
    "simple": prompt_simple,
}


# ── CLI 인자 해석 ──────────────────────────────────────────────


class LabelingConfig:
    """해석된 CLI 설정."""

    def __init__(self):
        self.dirs: list[Path] = []       # 대상 ROI 폴더들
        self.roi: str = ""               # ROI 이름
        self.mode: str = ""              # champion | structured | simple
        self.csv_path: Path | None = None  # 출력 CSV 경로
        self.overwrite: bool = False
        self.no_display: bool = False
        self.is_combined: bool = False   # 여러 폴더 통합 여부


def resolve_config(args, parser) -> LabelingConfig:
    cfg = LabelingConfig()
    cfg.overwrite = args.overwrite
    cfg.no_display = args.no_display

    if args.shop:
        # --shop 모드: 세션 폴더 아래 shop_slot_1~5 자동 탐색
        if not args.target_dirs:
            parser.error("--shop 사용 시 세션 폴더 경로를 입력해 주세요.")
        session_dir = Path(args.target_dirs[0])
        if not session_dir.is_dir():
            parser.error(f"세션 폴더 없음: {session_dir}")
        cfg.dirs = find_shop_dirs(session_dir)
        if not cfg.dirs:
            parser.error(
                f"shop_slot_1~5 폴더를 찾을 수 없음: {session_dir}\n"
                f"  shop_slot_1 디렉토리가 session 폴더 아래에 있어야 합니다."
            )
        cfg.roi = "shop_card"
        cfg.mode = "champion"
        cfg.csv_path = session_dir / "labels_shop_card.csv"
        cfg.is_combined = True
        return cfg

    # 다중/단일 폴더 모드
    if not args.target_dirs:
        parser.error(
            "대상 폴더를 입력해 주세요. (--shop 옵션으로 상점 슬롯 통합 가능)"
        )
    if not args.roi:
        parser.error("--roi 옵션이 필요합니다. (예: --roi shop_card, my_board)")

    cfg.roi = args.roi
    cfg.mode = get_mode_name(args.roi)
    cfg.dirs = [Path(d) for d in args.target_dirs]

    for d in cfg.dirs:
        if not d.is_dir():
            parser.error(f"폴더 없음: {d}")

    cfg.is_combined = len(cfg.dirs) > 1

    if cfg.is_combined:
        # 통합 CSV: 첫 번째 폴더의 부모 디렉토리에 저장
        parent = cfg.dirs[0].parent
        cfg.csv_path = parent / f"labels_{cfg.roi}.csv"
    else:
        # 단일 폴더: 기존 방식 (폴더 내 labels.csv)
        cfg.csv_path = cfg.dirs[0] / "labels.csv"

    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — 수동 데이터 레이블링 도구 (다중 폴더 지원)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target_dirs", nargs="*",
        help="레이블링할 이미지 폴더 경로(들). --shop 사용 시 세션 폴더 경로",
    )
    parser.add_argument(
        "--roi", type=str, default=None,
        help="ROI 이름 (예: shop_card, shop_slot_1, my_board, player_gold)",
    )
    parser.add_argument(
        "--shop", action="store_true",
        help="상점 5개 슬롯 통합 라벨링 (shop_slot_1~5 → shop_card)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="기존 label 덮어쓰기 허용",
    )
    parser.add_argument(
        "--no-display", action="store_true",
        help="이미지 표시 창 없이 경로만 출력",
    )
    args = parser.parse_args()

    cfg = resolve_config(args, parser)
    assert cfg.csv_path is not None, "Internal error: csv_path not resolved"
    aliases = _load_aliases()
    prompt_fn = PROMPT_DISPATCH[cfg.mode]

    # 이미지 수집
    items = collect_images(cfg.dirs, cfg.roi)
    if not items:
        print(f"이미지 파일이 없습니다.")
        for d in cfg.dirs:
            print(f"  확인한 폴더: {d}")
        sys.exit(0)

    # 기존 레이블 로드
    existing = load_existing_labels(cfg.csv_path)

    # 라벨링 대상 필터링
    already_labeled = 0
    to_label: list[dict] = []
    for item in items:
        if item["image_path"] in existing and not cfg.overwrite:
            already_labeled += 1
            continue
        to_label.append(item)

    # 시작 정보 출력
    print(f"{'='*62}")
    print(f"  TFT Vision — 수동 레이블링")
    print(f"{'='*62}")
    print(f"  ROI:       {cfg.roi}  ({cfg.mode} 모드)")
    print(f"  대상 폴더: {len(cfg.dirs)}개")
    for d in cfg.dirs:
        slot = detect_slot(d)
        info = f"  - {d}"
        if slot:
            info += f"  (slot {slot})"
        print(info)
    print(f"  CSV:       {cfg.csv_path}")
    print(f"  통합:      {'예' if cfg.is_combined else '아니오'}")
    print(f"  정규화:    {'champion_aliases.json 사용' if aliases else '없음'}")
    print(f"  총 이미지: {len(items)}개")
    print(f"  기존 레이블: {len(existing)}개")
    if not cfg.overwrite:
        print(f"  건너뜀:    {already_labeled}개")
    print(f"  대상:      {len(to_label)}개")
    print(f"  덮어쓰기:  {'예' if cfg.overwrite else '아니오'}")
    print(f"{'='*62}")

    if not to_label:
        print("\n✅ 모든 이미지가 이미 레이블링되었습니다.")
        sys.exit(0)

    if not is_interactive_terminal():
        print("\n⚠️  대화형 터미널이 아닙니다.")
        sys.exit(1)

    all_rows = list(existing.values())
    new_count = 0
    skipped_count = 0

    try:
        for i, item in enumerate(to_label, 1):
            img_path = item["path"]
            img_rel = item["image_path"]
            img_slot = item["slot"]
            img_roi = item["roi"]
            existing_row = existing.get(img_rel)

            # 슬롯 정보 표시
            slot_tag = f" [slot {img_slot}]" if img_slot else ""

            print(f"\n{'─'*62}")
            print(f"  [{i}/{len(to_label)}]{slot_tag} {img_rel}")

            show_ok = False
            if not cfg.no_display:
                show_ok = try_show_image(img_path, img_roi, i, len(to_label))
            if cfg.no_display or not show_ok:
                print(f"  크기: {img_path.stat().st_size} bytes")

            result = prompt_fn(existing_row)

            if result is None:
                skipped_count += 1
                print("  — 건너뜀")
                continue
            if result.get("_quit"):
                print("  — 저장 후 종료")
                break
            if result.get("_quit_immediate"):
                print("  — 즉시 종료")
                break

            raw_input = result.get("label_raw", "")
            normalized = normalize_label_text(raw_input, cfg.mode, aliases)

            row = {
                "image_path": img_rel,
                "roi": img_roi,
                "slot": img_slot,
                "champion": normalized.get("champion", ""),
                "star_level": normalized.get("star_level", ""),
                "items": result.get("items", ""),
                "position": result.get("position", ""),
                "label_raw": raw_input,
                "label_normalized": normalized.get("label_normalized", raw_input),
                "notes": result.get("notes", ""),
                "created_at": datetime.now().isoformat(),
            }
            all_rows.append(row)
            write_all_rows(cfg.csv_path, all_rows)
            new_count += 1

            info_parts = [f"raw='{raw_input}'"]
            norm_val = normalized.get("label_normalized", "")
            if norm_val and norm_val != raw_input:
                info_parts.append(f"→ '{norm_val}'")
            print(f"  ✓ {'  '.join(info_parts)}")

    except KeyboardInterrupt:
        print("\n  — 사용자 중단 (Ctrl+C)")
    finally:
        try:
            import cv2
            cv2.destroyAllWindows()
        except Exception:
            pass

    print(f"\n{'='*62}")
    print(f"  레이블링 완료!")
    print(f"  새 레이블: {new_count}개")
    if skipped_count > 0:
        print(f"  건너뜀:    {skipped_count}개")
    print(f"  CSV 파일:  {cfg.csv_path}")
    print(f"  모드:      {cfg.mode}")
    if aliases:
        print(f"  정규화:   {len(aliases)}개 alias 적용 가능")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
