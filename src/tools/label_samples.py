#!/usr/bin/env python3
"""TFT Vision — 수동 데이터 레이블링 CLI 도구 (구조화 레이블 지원).

ROI 유형에 따라 세 가지 모드로 동작:
  - champion 모드 (shop_slot_*): 챔피언 이름만 입력
  - structured 모드 (board/bench): 기물 목록을 champ_starLevel 형식으로 입력
  - simple 모드 (기타 ROI): 자유 텍스트 레이블

사용법:
    # 상점 슬롯 1 레이블링 (champion 모드)
    python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1

    # 내 보드 레이블링 (structured 모드)
    python -m src.tools.label_samples samples/session_xxx/my_board --roi my_board

    # 골드 숫자 레이블링 (simple 모드)
    python -m src.tools.label_samples samples/session_xxx/player_gold --roi player_gold
"""

import argparse
import csv
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
    "label",
    "notes",
    "created_at",
]

# ── ROI 모드 분류 ──────────────────────────────────────────────

# structured 모드: 보드/벤치 (여러 기물, star_level 포함)
STRUCTURED_ROIS = {
    "my_board", "my_bench",
    "enemy_board", "enemy_bench",
}

# champion 모드: 상점 슬롯 (챔피언 이름 단일)
def _is_champion_roi(roi: str) -> bool:
    return roi.startswith("shop_slot")


# ── CSV I/O ────────────────────────────────────────────────────


def load_existing_labels(csv_path: Path) -> dict[str, dict]:
    """기존 labels.csv 로드 → {image_path: row_dict}.

    구 포맷(5컬럼)이면 신 포맷(9컬럼)으로 자동 마이그레이션 후 파일 재작성.
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

    # 마이그레이션 필요한지 확인
    needs_migration = not set(CSV_FIELDS).issubset(existing_fields)

    for row in rows:
        if needs_migration:
            new_row = {}
            for field in CSV_FIELDS:
                new_row[field] = row.get(field, "")
            labels[row["image_path"]] = new_row
        else:
            labels[row["image_path"]] = dict(row)

    # 마이그레이션 필요 시 파일 재작성
    if needs_migration:
        logger.info(
            "CSV 포맷 마이그레이션: %d개 row → %d 컬럼",
            len(rows), len(CSV_FIELDS),
        )
        write_all_rows(csv_path, list(labels.values()))

    return labels


def write_all_rows(csv_path: Path, rows: list[dict]):
    """전체 rows를 CSV_FIELDS 포맷으로 덮어쓰기."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            writer.writerow(out)


# ── 이미지 유틸 ────────────────────────────────────────────────


def get_image_files(target_dir: Path) -> list[Path]:
    """이미지 파일 목록 (파일명 기준 정렬)."""
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    return sorted(p for p in target_dir.iterdir() if p.suffix.lower() in exts)


def try_show_image(image_path: Path, roi: str, index: int, total: int) -> bool:
    """cv2로 이미지 표시 시도. 실패 시 False."""
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


# ── 입력 파싱 ──────────────────────────────────────────────────


def parse_structured(raw: str) -> dict:
    """structured 모드 입력 파싱.

    'ahri_2,yasuo_1,lux_unknown' →
        champion='ahri,yasuo,lux'
        star_level='2,1,unknown'
        label='ahri_2,yasuo_1,lux_unknown'
    """
    text = raw.strip()
    if not text:
        return {"champion": "", "star_level": "", "label": ""}

    # 전체 입력이 unknown/bad인 경우
    if text in ("unknown", "bad"):
        return {"champion": text, "star_level": "", "label": text}

    units = [u.strip() for u in text.split(",") if u.strip()]
    champs: list[str] = []
    stars: list[str] = []

    for unit in units:
        if "_" in unit:
            champ_part, sep, star_part = unit.rpartition("_")
            if star_part in ("1", "2", "3", "unknown"):
                champs.append(champ_part if champ_part else unit)
                stars.append(star_part)
            else:
                champs.append(unit)
                stars.append("unknown")
        else:
            champs.append(unit)
            stars.append("unknown")

    return {
        "champion": ",".join(champs),
        "star_level": ",".join(stars),
        "label": text,
    }


# ── 프롬프트 ───────────────────────────────────────────────────


def show_existing_info(row: dict | None) -> str:
    """기존 레이블 정보 문자열."""
    if not row:
        return ""
    parts = []
    champ = row.get("champion", "").strip()
    star = row.get("star_level", "").strip()
    label = row.get("label", "").strip()
    if champ and star:
        parts.append(f"champion='{champ}' star='{star}'")
    elif champ:
        parts.append(f"champion='{champ}'")
    elif label:
        parts.append(f"label='{label}'")
    if row.get("notes", "").strip():
        parts.append(f"notes='{row['notes'].strip()}'")
    return f"  기존: {' | '.join(parts)}" if parts else ""


def prompt_champion(
    existing_row: dict | None,
) -> dict | None:
    """champion 모드 프롬프트. None=skip/quit."""
    info = show_existing_info(existing_row)
    if info:
        print(info)

    inp = input(
        "  [champion] name (Enter=skip, q=quit, qq=immediate, unknown, bad): "
    ).strip()
    if not inp:
        return None  # skip
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}

    label = inp
    champion = inp
    return {
        "champion": champion,
        "star_level": "",
        "items": "",
        "position": "",
        "label": label,
    }


def prompt_structured(
    existing_row: dict | None,
) -> dict | None:
    """structured 모드 프롬프트. None=skip/quit."""
    info = show_existing_info(existing_row)
    if info:
        print(info)
    print("  형식: champ_starLevel,champ_starLevel,...  (예: ahri_2,yasuo_1)")
    print("  star: 1|2|3|unknown  |  champion: unknown|bad  |  Enter=skip")

    inp = input("  [units] (q=quit, qq=immediate): ").strip()
    if not inp:
        return None  # skip
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}

    parsed = parse_structured(inp)
    # notes는 별도로 묻지 않고 label 시간에 같이 처리
    notes = input("  [notes] (Enter=none): ").strip()

    parsed["items"] = ""
    parsed["position"] = ""
    parsed["notes"] = notes
    return parsed


def prompt_simple(
    existing_row: dict | None,
) -> dict | None:
    """simple 모드 프롬프트. None=skip/quit."""
    info = show_existing_info(existing_row)
    if info:
        print(info)

    inp = input("  [label] (Enter=skip, q=quit, qq=immediate): ").strip()
    if not inp:
        return None  # skip
    if inp.lower() == "q":
        return {"_quit": True}
    if inp.lower() == "qq":
        return {"_quit_immediate": True}

    return {
        "champion": "",
        "star_level": "",
        "items": "",
        "position": "",
        "label": inp,
    }


# ── 프롬프트 디스패치 ──────────────────────────────────────────


def get_mode_name(roi: str) -> str:
    if _is_champion_roi(roi):
        return "champion"
    if roi in STRUCTURED_ROIS:
        return "structured"
    return "simple"


PROMPT_DISPATCH = {
    "champion": prompt_champion,
    "structured": prompt_structured,
    "simple": prompt_simple,
}


# ── 메인 ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — 수동 데이터 레이블링 도구 (구조화 레이블)",
        epilog=(
            "예시:\n"
            "  python -m src.tools.label_samples samples/xxx/shop_slot_1 --roi shop_slot_1\n"
            "  python -m src.tools.label_samples samples/xxx/my_board --roi my_board\n"
            "  python -m src.tools.label_samples samples/xxx/player_gold --roi player_gold"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target_dir", type=str,
        help="레이블링할 이미지 폴더 경로",
    )
    parser.add_argument(
        "--roi", type=str, required=True,
        help="ROI 이름 (예: shop_slot_1, my_board, player_gold)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="기존 label 덮어쓰기 허용 (기본: 이미 label된 이미지 건너뜀)",
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

    csv_path = target_dir / "labels.csv"
    existing = load_existing_labels(csv_path)
    image_files = get_image_files(target_dir)

    if not image_files:
        print(f"이미지 파일이 없습니다: {target_dir}")
        sys.exit(0)

    # 대상 이미지 필터링
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
    print(f"  총 이미지:      {len(image_files)}")
    print(f"  기존 레이블:    {len(existing)}")
    if not args.overwrite:
        print(f"  건너뛸 이미지:  {already_labeled}")
    print(f"  레이블링 대상:  {len(to_label)}")
    print(f"  덮어쓰기:       {'예' if args.overwrite else '아니오'}")
    print(f"{'='*62}")

    if not to_label:
        print("\n✅ 모든 이미지가 이미 레이블링되었습니다.")
        print("   --overwrite 옵션으로 기존 레이블을 수정할 수 있습니다.")
        sys.exit(0)

    if not is_interactive_terminal():
        print("\n⚠️  대화형 터미널이 아닙니다. 레이블링을 진행할 수 없습니다.")
        sys.exit(1)

    # Load full rows list for saving (in-memory)
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

            # 모드별 프롬프트
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

            # 레이블 저장
            row = {
                "image_path": name,
                "roi": roi,
                "champion": result.get("champion", ""),
                "star_level": result.get("star_level", ""),
                "items": result.get("items", ""),
                "position": result.get("position", ""),
                "label": result.get("label", ""),
                "notes": result.get("notes", ""),
                "created_at": datetime.now().isoformat(),
            }
            all_rows.append(row)
            write_all_rows(csv_path, all_rows)
            new_count += 1
            print(f"  ✓ 저장")

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
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
