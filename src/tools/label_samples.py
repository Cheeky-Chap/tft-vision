#!/usr/bin/env python3
"""TFT Vision — 수동 데이터 레이블링 CLI 도구.

수집된 샘플 이미지를 사람이 보고 직접 label(정답)을 입력하여
labels.csv로 저장합니다. 향후 OCR/이미지 인식 모델 학습 데이터로 활용됩니다.

사용법:
    # 상점 슬롯 1 레이블링
    python -m src.tools.label_samples samples/session_20260704_153000/shop_slot_1 --roi shop_slot_1

    # 내 보드 레이블링 (기존 레이블 덮어쓰기)
    python -m src.tools.label_samples samples/session_20260704_153000/my_board --roi my_board --overwrite

    # 이미지 표시 없이 경로만 출력
    python -m src.tools.label_samples samples/session_20260704_153000/shop_slot_2 --roi shop_slot_2 --no-display
"""

import argparse
import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("tft-vision.label_samples")

CSV_FIELDS = ["image_path", "roi", "label", "notes", "created_at"]


def load_existing_labels(csv_path: Path) -> dict:
    """기존 labels.csv 로드 → {image_path: row_dict}."""
    labels: dict[str, dict] = {}
    if not csv_path.exists():
        return labels
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels[row["image_path"]] = row
    return labels


def append_label(csv_path: Path, row: dict):
    """단일 레이블을 CSV에 추가 저장 (헤더는 최초 1회만)."""
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


def get_image_files(target_dir: Path) -> list[Path]:
    """이미지 파일 목록 (파일명 기준 정렬)."""
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    files = sorted([p for p in target_dir.iterdir() if p.suffix.lower() in exts])
    return files


def try_show_image(image_path: Path, roi: str, index: int, total: int):
    """cv2로 이미지 표시 시도 (실패 시 무시)."""
    try:
        import cv2

        img = cv2.imread(str(image_path))
        if img is not None:
            h, w = img.shape[:2]
            # 화면에 맞게 리사이즈 (너무 큰 경우)
            display_w, display_h = w, h
            if max(w, h) > 800:
                scale = 800.0 / max(w, h)
                display_w = int(w * scale)
                display_h = int(h * scale)
                display = cv2.resize(img, (display_w, display_h))
            else:
                display = img.copy()
            cv2.imshow(f"Label: {roi} ({index}/{total})", display)
            cv2.waitKey(1)
            return True
    except Exception:
        pass
    return False


def is_interactive_terminal() -> bool:
    """터미널이 대화형인지 확인."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def format_label_history(existing: dict, image_name: str) -> str:
    """기존 레이블이 있으면 표시."""
    row = existing.get(image_name)
    if row:
        label = row.get("label", "").strip()
        notes = row.get("notes", "").strip()
        if notes:
            return f"  기존: label='{label}' notes='{notes}'"
        return f"  기존: label='{label}'"
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — 수동 데이터 레이블링 도구",
        epilog=(
            "예시:\n"
            "  python -m src.tools.label_samples samples/session_xxx/shop_slot_1 --roi shop_slot_1\n"
            "  python -m src.tools.label_samples samples/session_xxx/my_board --roi my_board --overwrite\n"
            "  python -m src.tools.label_samples samples/session_xxx/shop_slot_3 --roi shop_slot_3 --no-display"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target_dir",
        type=str,
        help="레이블링할 이미지 폴더 경로 (예: samples/session_xxx/shop_slot_1)",
    )
    parser.add_argument(
        "--roi",
        type=str,
        required=True,
        help="ROI 이름 (예: shop_slot_1, my_board, my_bench, player_gold, stage_info)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 label 덮어쓰기 허용 (기본: 이미 label된 이미지 건너뜀)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="이미지 표시 창 없이 경로만 출력 (SSH/원격 터미널용)",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    if not target_dir.is_dir():
        print(f"오류: 디렉토리가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

    csv_path = target_dir / "labels.csv"
    existing = load_existing_labels(csv_path)
    image_files = get_image_files(target_dir)

    if not image_files:
        print(f"이미지 파일이 없습니다: {target_dir}")
        sys.exit(0)

    # 대상 이미지 필터링
    already_labeled = 0
    to_label = []
    for img_path in image_files:
        name = img_path.name
        if name in existing and not args.overwrite:
            already_labeled += 1
            continue
        to_label.append(img_path)

    print(f"{'='*60}")
    print(f"  TFT Vision — 수동 레이블링")
    print(f"{'='*60}")
    print(f"  대상: {target_dir}")
    print(f"  ROI:  {args.roi}")
    print(f"  CSV:  {csv_path}")
    print(f"  총 이미지:      {len(image_files)}")
    print(f"  기존 레이블:    {len(existing)}")
    if not args.overwrite:
        print(f"  건너뛸 이미지:  {already_labeled}")
    print(f"  레이블링 대상:  {len(to_label)}")
    print(f"  덮어쓰기:       {'예' if args.overwrite else '아니오'}")
    print(f"{'='*60}")

    if not to_label:
        print("\n✅ 모든 이미지가 이미 레이블링되었습니다.")
        print("   --overwrite 옵션으로 기존 레이블을 수정할 수 있습니다.")
        sys.exit(0)

    if not is_interactive_terminal():
        print("\n⚠️  대화형 터미널이 아닙니다. 레이블링을 진행할 수 없습니다.")
        print("   이 도구는 stdin/stdout이 터미널인 환경에서만 동작합니다.")
        sys.exit(1)

    # 메인 레이블링 루프
    new_count = 0
    skipped_count = 0

    try:
        for i, img_path in enumerate(to_label, 1):
            name = img_path.name
            existing_info = format_label_history(existing, name)

            print(f"\n{'─'*60}")
            print(f"  [{i}/{len(to_label)}] {name}")
            if existing_info:
                print(existing_info)
            print(f"  경로: {img_path.relative_to(target_dir.parent)}")

            # 이미지 표시
            show_ok = False
            if not args.no_display:
                show_ok = try_show_image(img_path, args.roi, i, len(to_label))
            if args.no_display or not show_ok:
                print(f"  크기: {img_path.stat().st_size} bytes")

            # label 입력
            while True:
                inp = input(f"  [{args.roi}] label (Enter=건너뜀, q=종료): ").strip()
                if inp == "":
                    # 건너뜀
                    skipped_count += 1
                    print(f"  — 건너뜀")
                    break
                if inp.lower() == "q":
                    print(f"  — 저장 후 종료")
                    # 마무리 후 break
                    raise StopIteration()  # goto finally
                if inp.lower() == "qq":
                    print(f"  — 즉시 종료 (마지막 label 미저장)")
                    new_count -= 1  # 이전 label은 이미 저장됨
                    raise StopIteration()

                label = inp

                # notes 입력 (선택)
                notes_inp = input(f"  [{args.roi}] notes (Enter=없음): ").strip()

                row = {
                    "image_path": name,
                    "roi": args.roi,
                    "label": label,
                    "notes": notes_inp,
                    "created_at": datetime.now().isoformat(),
                }
                append_label(csv_path, row)
                new_count += 1
                print(f"  ✓ 저장됨: {label}")
                break

    except StopIteration:
        pass
    except KeyboardInterrupt:
        print(f"\n  — 사용자 중단 (Ctrl+C)")
    finally:
        try:
            import cv2

            cv2.destroyAllWindows()
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"  레이블링 완료!")
    print(f"  새 레이블: {new_count}개")
    if skipped_count > 0:
        print(f"  건너뜀:    {skipped_count}개 (레이블 미입력)")
    print(f"  CSV 파일:  {csv_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
