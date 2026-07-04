"""TFT Vision — Unit-level 보드/벤치 라벨링 도구.

체력바 중심 클릭 방식으로 기물 단위 데이터를 수집합니다.

사용법:
    python -m src.tools.label_units samples/session_xxx/my_board --roi my_board
    python -m src.tools.label_units samples/session_xxx/my_bench --roi my_bench
    python -m src.tools.label_units samples/session_xxx/enemy_board --roi enemy_board
    python -m src.tools.label_units samples/session_xxx/enemy_bench --roi enemy_bench
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("tft-vision.label_units")

CSV_FIELDS = [
    "image_path",
    "roi",
    "champion_raw",
    "champion_normalized",
    "star_level",
    "healthbar_x",
    "healthbar_y",
    "items",
    "notes",
    "created_at",
]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

MAX_DISPLAY_SIZE = 800  # px, 긴 쪽 기준 리사이즈

# ── 챔피언명 정규화 ────────────────────────────────────────────

_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "champion_aliases.json"

SPECIAL_MAP: dict[str, str] = {
    "모름": "unknown",
    "잘못됨": "bad",
}


def _load_aliases() -> dict[str, str]:
    if not _ALIASES_PATH.exists():
        return {}
    try:
        with open(_ALIASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("aliases", {})
    except (json.JSONDecodeError, OSError):
        return {}


def normalize_champion_name(raw: str, aliases: dict[str, str]) -> str:
    k = raw.strip()
    if not k:
        return k
    if k in SPECIAL_MAP:
        return SPECIAL_MAP[k]
    if k in aliases:
        return aliases[k]
    return k


# ── CSV I/O ────────────────────────────────────────────────────


def load_existing_labels(csv_path: Path) -> list[dict]:
    """전체 레이블 로드. 없으면 빈 리스트."""
    if not csv_path.exists():
        return []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_all_rows(csv_path: Path, rows: list[dict]):
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            writer.writerow(out)


# ── 이미지 수집 ────────────────────────────────────────────────


def collect_images(target_dir: Path) -> list[Path]:
    return sorted(p for p in target_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)


# ── OpenCV 상호작용 ───────────────────────────────────────────

_click_point: tuple[int, int] | None = None


def _mouse_callback(event, x, y, flags, param):
    global _click_point
    if event == cv2.EVENT_LBUTTONDOWN:
        _click_point = (x, y)


def _load_and_resize(path: Path):
    """이미지 로드 + MAX_DISPLAY_SIZE 이하로 리사이즈. (img, display, scale) 반환."""
    img = cv2.imread(str(path))
    if img is None:
        return None, None, 1.0
    h, w = img.shape[:2]
    scale = min(MAX_DISPLAY_SIZE / max(w, h), 1.0)
    if scale < 1.0:
        display = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        display = img.copy()
    return img, display, scale


def _draw_units(image: np.ndarray, units: list[dict], scale: float, color=(0, 255, 0)):
    """기존 라벨링 위치를 이미지 위에 표시."""
    for unit in units:
        try:
            sx = int(float(unit.get("healthbar_x", 0)) * scale)
            sy = int(float(unit.get("healthbar_y", 0)) * scale)
        except (ValueError, TypeError):
            continue
        cv2.circle(image, (sx, sy), 6, color, -1)
        cv2.circle(image, (sx, sy), 6, (255, 255, 255), 1)  # 테두리
        label = unit.get("champion_normalized", "") or unit.get("champion_raw", "")
        star = unit.get("star_level", "")
        if star:
            label += f" ★{star}"
        if label:
            cv2.putText(image, label, (sx + 12, sy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)


def _draw_info(image: np.ndarray, item_idx: int, total: int, rel_path: str):
    """화면 상단/하단 정보 표시."""
    h, w = image.shape[:2]
    cv2.putText(image, f"  [{item_idx}/{total}] {rel_path}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(image, "  L-click=select  n=next  q=quit  Esc=immediate",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)


def wait_for_cv2_action(window_name: str, timeout_ms: int = 150):
    """OpenCV 창에서 사용자 입력 대기.
    Returns: ('click', x, y) | ('next',) | ('quit',) | ('quit_now',) | None
    """
    global _click_point

    key = cv2.waitKey(timeout_ms) & 0xFF

    if _click_point is not None:
        x, y = _click_point
        _click_point = None
        return ("click", x, y)

    if key == ord("n"):
        return ("next",)
    if key == ord("q"):
        return ("quit",)
    if key == 27:  # Esc
        return ("quit_now",)

    return None


# ── 터미널 프롬프트 ───────────────────────────────────────────


def prompt_champion(existing_count: int) -> tuple:
    """챔피언명 입력. Returns: ('champ', name) | ('skip',) | ('cmd', cmd)

    Commands: next, undo, quit, quit_now
    """
    inp = input(
        "  champion (Enter=skip, u=undo, n=done, q=quit, qq=immediate): "
    ).strip()
    if not inp:
        return ("skip",)
    low = inp.lower()
    if low == "n":
        return ("cmd", "next")
    if low == "u":
        return ("cmd", "undo")
    if low == "q":
        return ("cmd", "quit")
    if low == "qq":
        return ("cmd", "quit_now")
    return ("champ", inp)


def prompt_star() -> str:
    star = input("  star_level (1/2/3/unknown, Enter=unknown): ").strip()
    if star in ("1", "2", "3", "unknown"):
        return star
    return "unknown"


def prompt_items() -> str:
    return input("  items (쉼표로 여러 개, Enter=none): ").strip()


def prompt_notes() -> str:
    return input("  notes (Enter=none): ").strip()


# ── 메인 ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="TFT Vision — Unit-level 보드/벤치 라벨링 (체력바 클릭 방식)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target_dir", type=str, help="레이블링할 이미지 폴더 경로")
    parser.add_argument(
        "--roi", type=str, required=True,
        help="ROI 이름 (my_board, my_bench, enemy_board, enemy_bench)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="기존 라벨 무시하고 재라벨링",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    if not target_dir.is_dir():
        print(f"오류: 디렉토리 없음: {target_dir}")
        sys.exit(1)

    roi = args.roi
    aliases = _load_aliases()
    csv_path = target_dir / "labels.csv"

    # 이미지 수집
    image_files = collect_images(target_dir)
    if not image_files:
        print(f"이미지 파일 없음: {target_dir}")
        sys.exit(0)

    # 기존 레이블 로드
    existing_rows = load_existing_labels(csv_path)
    existing_by_image: dict[str, list[dict]] = {}
    for r in existing_rows:
        key = r.get("image_path", "")
        existing_by_image.setdefault(key, []).append(r)

    print(f"{'='*62}")
    print(f"  TFT Vision — Unit-level 라벨링")
    print(f"{'='*62}")
    print(f"  폴더:    {target_dir}")
    print(f"  ROI:     {roi}")
    print(f"  CSV:     {csv_path}")
    print(f"  이미지:  {len(image_files)}개")
    print(f"  기존 유닛: {len(existing_rows)}개")
    print(f"  정규화: {'champion_aliases.json' if aliases else '없음'}")
    print(f"{'='*62}")
    print(f"  조작:")
    print(f"    좌클릭 = 체력바 중심 선택")
    print(f"    n      = 다음 이미지")
    print(f"    q      = 저장 후 종료")
    print(f"    Esc    = 즉시 종료")
    print(f"    u      = 마지막 입력 취소 (터미널)")
    print(f"{'='*62}")
    print()

    window_name = f"Label Units — {roi}"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, _mouse_callback)

    all_rows = list(existing_rows)
    new_count = 0
    skipped_images = 0

    try:
        for idx, img_path in enumerate(image_files, 1):
            name = img_path.name

            # 기존 유닛 확인 (정보용)
            existing_units = existing_by_image.get(name, [])
            if existing_units:
                print(f"  [{idx}/{len(image_files)}] {name} — 기존 {len(existing_units)}개 유닛 (추가 라벨링 가능)")

            img_orig, img_display, scale = _load_and_resize(img_path)
            if img_orig is None:
                print(f"  이미지 로드 실패: {img_path}")
                continue

            print(f"\n{'─'*62}")
            print(f"  [{idx}/{len(image_files)}] {name}")
            print(f"  체력바 중심을 클릭하세요. (n=다음, q=종료, Esc=즉시종료)")

            # 현재 이미지에서 새로 추가한 유닛 (undo용)
            new_units_this_image: list[dict] = []
            done_with_image = False
            quit_session = False
            quit_immediate = False

            while not done_with_image:
                # 화면 갱신
                canvas = img_display.copy()
                # 기존 유닛 표시 (녹색)
                _draw_units(canvas, existing_units, scale, color=(0, 200, 0))
                # 새로 추가한 유닛 표시 (청록)
                _draw_units(canvas, new_units_this_image, scale, color=(0, 255, 255))
                _draw_info(canvas, idx, len(image_files), name)
                cv2.imshow(window_name, canvas)

                action = wait_for_cv2_action(window_name)

                if action is None:
                    continue

                if action[0] == "next":
                    done_with_image = True
                    break

                if action[0] == "quit":
                    quit_session = True
                    done_with_image = True
                    break

                if action[0] == "quit_now":
                    quit_immediate = True
                    done_with_image = True
                    break

                if action[0] == "click":
                    _, cx, cy = action
                    ox = int(round(cx / scale))
                    oy = int(round(cy / scale))

                    print(f"\n  📍 ({ox}, {oy}) — 유닛 정보 입력:")

                    # 챔피언 프롬프트
                    result = prompt_champion(len(new_units_this_image))
                    if result[0] == "skip":
                        print("  — 취소 (클릭 무시)")
                        continue
                    if result[0] == "cmd":
                        cmd = result[1]
                        if cmd == "next":
                            done_with_image = True
                            break
                        if cmd == "undo":
                            if new_units_this_image:
                                undone = new_units_this_image.pop()
                                all_rows.pop()  # 방금 추가된 행 제거
                                raw = undone.get("champion_raw", "?")
                                print(f"  ↩ 취소됨: {raw}")
                            else:
                                print("  취소할 항목 없음")
                            continue
                        if cmd == "quit":
                            quit_session = True
                            done_with_image = True
                            break
                        if cmd == "quit_now":
                            quit_immediate = True
                            done_with_image = True
                            break

                    champ_raw = result[1]
                    star = prompt_star()
                    items = prompt_items()
                    notes = prompt_notes()

                    champ_norm = normalize_champion_name(champ_raw, aliases)

                    row = {
                        "image_path": name,
                        "roi": roi,
                        "champion_raw": champ_raw,
                        "champion_normalized": champ_norm,
                        "star_level": star,
                        "healthbar_x": str(ox),
                        "healthbar_y": str(oy),
                        "items": items,
                        "notes": notes,
                        "created_at": datetime.now().isoformat(),
                    }

                    new_units_this_image.append(row)
                    all_rows.append(row)
                    write_all_rows(csv_path, all_rows)
                    new_count += 1

                    display_star = f"★{star}" if star else ""
                    norm_tag = f" → {champ_norm}" if champ_norm != champ_raw else ""
                    print(f"  ✓ {champ_raw}{norm_tag} {display_star} @ ({ox}, {oy})")
                    print(f"    계속: 클릭 또는 n=다음, q=종료")

            # 이미지 루프 종료
            if quit_session or quit_immediate:
                if quit_session:
                    print("\n  저장 후 종료합니다.")
                else:
                    print("\n  즉시 종료합니다.")
                break

    except KeyboardInterrupt:
        print("\n  — 사용자 중단")
    finally:
        cv2.destroyAllWindows()

    # 최종 통계
    print(f"\n{'='*62}")
    print(f"  완료!")
    print(f"  새 유닛:      {new_count}개")
    if skipped_images > 0:
        print(f"  건너뜀:       {skipped_images}개")
    print(f"  총 유닛:      {len(all_rows)}개")
    print(f"  CSV 파일:     {csv_path}")
    print(f"  ROI:          {roi}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
