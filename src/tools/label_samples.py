#!/usr/bin/env python3
"""TFT Vision — 수동 데이터 레이블링 CLI 도구 (한글 입력 + 정규화 지원).

ROI 유형에 따라 세 가지 모드로 동작:
  - champion 모드 (shop_slot_*): 챔피언 이름만 입력 (한글 가능)
  - structured 모드 (board/bench): 기물 목록을 champ_starLevel 형식으로 입력
  - simple 모드 (기타 ROI): 자유 텍스트 레이블

한글 챔피언명을 입력하면 champion_aliases.json 매핑을 통해
내부적으로 영문 canonical id로 정규화하여 저장합니다.

사용법:
    python -m src.tools.label_samples samples/xxx/shop_slot_1 --roi shop_slot_1
    python -m src.tools.label_samples samples/xxx/my_board --roi my_board
"""

import argparse
import csv
import json
import logging
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
    "champion",
    "star_level",
    "items",
    "position",
    "label_raw",
    "label_normalized",
    "notes",
    "created_at",
]

# ── 챔피언명 정규화 ────────────────────────────────────────────

_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "champion_aliases.json"

# 특수값: 이 값들은 정규화되어 저장됨
SPECIAL_MAP: dict[str, str] = {
    "모름": "unknown",
    "잘못됨": "bad",
}


def _load_aliases() -> dict[str, str]:
    """한글→영문 챔피언 매핑 로드."""
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
    """한글/입력 챔피언명 → 영문 canonical id.

    우선순위: special > alias > 원본 유지
    """
    k = korean_name.strip()
    if not k:
        return k
    # 특수값 먼저
    if k in SPECIAL_MAP:
        return SPECIAL_MAP[k]
    # alias 매핑
    if k in aliases:
        return aliases[k]
    # 이미 영문이거나 매핑 없는 경우 원본 유지
    return k


# ── 라벨 정규화 ────────────────────────────────────────────────


def normalize_label_text(raw: str, mode: str, aliases: dict[str, str]) -> dict:
    """사용자 입력 원본 → 정규화 결과.

    Returns:
        dict with keys: champion, star_level, label_normalized
    """
    text = raw.strip()
    if not text:
        return {"champion": "", "star_level": "", "label_normalized": ""}

    if mode == "simple":
        return {"champion": "", "star_level": "", "label_normalized": text}

    if mode == "champion":
        norm = normalize_champion_name(text, aliases)
        return {"champion": norm, "star_level": "", "label_normalized": norm}

    # structured 모드
    if mode == "structured":
        # 전체 입력이 특수값인 경우
        if text in SPECIAL_MAP.values() or text in SPECIAL_MAP:
            norm = normalize_champion_name(text, aliases)
            return {
                "champion": norm,
                "star_level": "",
                "label_normalized": norm,
            }

        units = [u.strip() for u in text.split(",") if u.strip()]
        champs: list[str] = []
        stars: list[str] = []
        norm_units: list[str] = []

        for unit in units:
            if "_" in unit:
                champ_part, _, star_part = unit.rpartition("_")
                if star_part in ("1", "2", "3", "unknown"):
                    norm_champ = normalize_champion_name(champ_part, aliases)
                    champs.append(norm_champ)
                    stars.append(star_part)
                    norm_units.append(f"{norm_champ}_{star_part}")
                else:
                    # _가 있지만 star_level 패턴 아님 → 통째로 챔피언명
                    norm_champ = normalize_champion_name(unit, aliases)
                    champs.append(norm_champ)
                    stars.append("unknown")
                    norm_units.append(norm_champ)
            else:
                norm_champ = normalize_champion_name(unit, aliases)
                champs.append(norm_champ)
                stars.append("unknown")
                norm_units.append(norm_champ)

        return {
            "champion": ",".join(champs),
            "star_level": ",".join(stars),
            "label_normalized": ",".join(norm_units),
        }

    return {"champion": "", "star_level": "", "label_normalized": text}


# ── ROI 모드 분류 ──────────────────────────────────────────────

STRUCTURED_ROIS = {"my_board", "my_bench", "enemy_board", "enemy_bench"}


def _is_champion_roi(roi: str) -> bool:
    return roi.startswith("shop_slot")


def get_mode_name(roi: str) -> str:
    if _is_champion_roi(roi):
        return "champion"
    if roi in STRUCTURED_ROIS:
        return "structured"
    return "simple"


# ── CSV I/O ────────────────────────────────────────────────────


def load_existing_labels(csv_path: Path) -> dict[str, dict]:
    """기존 labels.csv 로드 → {image_path: row_dict}.

    구 포맷(label 컬럼)이면 label_raw/label_normalized로 마이그레이션.
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
                # 구포맷 label → label_raw + label_normalized
                if field == "label_raw":
                    label_val = row.get("label", "")
                    new_row["label_raw"] = label_val if label_val else val
                elif field == "label_normalized":
                    label_val = row.get("label", "")
                    new_row["label_normalized"] = label_val if label_val else val
                else:
                    new_row[field] = val
            labels[row["image_path"]] = new_row
        else:
            labels[row["image_path"]] = dict(row)

    if needs_migration:
        logger.info(
            "CSV 마이그레이션: %d개 row → %d 컬럼 (label→label_raw+label_normalized)",
            len(rows), len(CSV_FIELDS),
        )
        write_all_rows(csv_path, list(labels.values()))

    return labels


def write_all_rows(csv_path: Path, rows: list[dict]):
    """전체 rows를 CSV_FIELDS 포맷으로 덮어쓰기 (UTF-8)."""
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            writer.writerow(out)


# ── 이미지 유틸 ────────────────────────────────────────────────


def get_image_files(target_dir: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    return sorted(p for p in target_dir.iterdir() if p.suffix.lower() in exts)


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
    champ = row.get("champion", "").strip()
    star = row.get("star_level", "").strip()
    raw = row.get("label_raw", "").strip()
    norm = row.get("label_normalized", "").strip()
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
    """챔피언 모드: 한글/영문 챔피언명 입력."""
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
    """보드/벤치 모드: champ_starLevel,champ_starLevel,... 형식으로 입력."""
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
    """단순 텍스트 모드."""
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


# ── 프롬프트 디스패치 ──────────────────────────────────────────

PROMPT_DISPATCH = {
    "champion": prompt_champion,
    "structured": prompt_structured,
    "simple": prompt_simple,
}


# ── 메인 ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — 수동 데이터 레이블링 도구 (한글 입력+정규화)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target_dir", type=str, help="레이블링할 이미지 폴더 경로")
    parser.add_argument("--roi", type=str, required=True, help="ROI 이름")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="기존 label 덮어쓰기",
    )
    parser.add_argument(
        "--no-display", action="store_true",
        help="이미지 표시 창 없이 경로만 출력",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    if not target_dir.is_dir():
        print(f"오류: 디렉토리가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

    roi = args.roi
    mode = get_mode_name(roi)
    prompt_fn = PROMPT_DISPATCH[mode]
    aliases = _load_aliases()

    csv_path = target_dir / "labels.csv"
    existing = load_existing_labels(csv_path)
    image_files = get_image_files(target_dir)

    if not image_files:
        print(f"이미지 파일이 없습니다: {target_dir}")
        sys.exit(0)

    already_labeled = 0
    to_label: list[Path] = []
    for img_path in image_files:
        name = img_path.name
        if name in existing and not args.overwrite:
            already_labeled += 1
            continue
        to_label.append(img_path)

    print(f"{'='*62}")
    print(f"  TFT Vision — 수동 레이블링")
    print(f"{'='*62}")
    print(f"  대상:  {target_dir}")
    print(f"  ROI:   {roi}  ({mode} 모드)")
    print(f"  CSV:   {csv_path}")
    print(f"  정규화: {'champion_aliases.json 사용' if aliases else '없음'}")
    print(f"  총 이미지:      {len(image_files)}")
    print(f"  기존 레이블:    {len(existing)}")
    if not args.overwrite:
        print(f"  건너뛸 이미지:  {already_labeled}")
    print(f"  레이블링 대상:  {len(to_label)}")
    print(f"  덮어쓰기:       {'예' if args.overwrite else '아니오'}")
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
        for i, img_path in enumerate(to_label, 1):
            name = img_path.name
            existing_row = existing.get(name)

            print(f"\n{'─'*62}")
            print(f"  [{i}/{len(to_label)}] {name}")
            print(f"  경로: {img_path.relative_to(target_dir.parent)}")

            show_ok = False
            if not args.no_display:
                show_ok = try_show_image(img_path, roi, i, len(to_label))
            if args.no_display or not show_ok:
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

            # 정규화
            normalized = normalize_label_text(raw_input, mode, aliases)

            row = {
                "image_path": name,
                "roi": roi,
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
            write_all_rows(csv_path, all_rows)
            new_count += 1

            # 저장 확인 출력
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
    print(f"  CSV 파일:  {csv_path}")
    print(f"  모드:      {mode}")
    if aliases:
        print(f"  정규화:   {len(aliases)}개 alias 적용 가능")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
