"""
TFT Vision — ROI 검증 디버그 시각화.

Overlay: game frame 위에 ROI 사각형 + 이름 표시
Contact Sheet: 모든 ROI crop 결과를 한 장의 이미지로 합쳐 저장
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict

import cv2
import numpy as np

from src.crop.roi_definitions import ROI_REGIONS, list_roi_names

logger = logging.getLogger("tft-vision.debug_roi")

# ROI별 표시 색상 (BGR)
ROI_COLORS = {
    "item_area":      (255,   0, 255),  # magenta
    "player_level":   (255, 255,   0),  # cyan
    "player_gold":    (  0, 255, 255),  # yellow
    "player_streak":  (255, 128,   0),  # light blue
    "shop":           (  0, 255,   0),  # green
    "shop_slot_1":    ( 50, 200,  50),  # dark green
    "shop_slot_2":    (100, 200, 100),  # green shade
    "shop_slot_3":    (150, 200, 150),  # green shade
    "shop_slot_4":    (100, 200, 100),  # green shade
    "shop_slot_5":    ( 50, 200,  50),  # dark green
    "stage_info":     (255, 165,   0),  # orange
    "player_list":    (128,   0, 128),  # purple
    "enemy_bench":    (  0, 165, 255),  # orange-red
    "enemy_board":    (  0,   0, 255),  # red
    "my_board":       (  0, 255,   0),  # green
    "my_bench":       (  0, 200, 200),  # teal
    "full_screen":    (128, 128, 128),  # gray
}

DEFAULT_COLOR = (200, 200, 200)  # light gray for unknown ROIs


def draw_roi_overlay(
    image: np.ndarray,
    save_dir: str | Path = "debug/roi_overlay",
    roi_names: list | None = None,
) -> str:
    """게임 프레임 위에 ROI 사각형과 이름을 그려 저장.

    Args:
        image: game frame (numpy array, HWC BGR)
        save_dir: 저장 디렉터리
        roi_names: 표시할 ROI 목록 (None = 전체)

    Returns:
        저장된 파일 경로
    """
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    overlay = image.copy()
    names = roi_names or list_roi_names()

    for name in names:
        region = ROI_REGIONS.get(name)
        if not region or name == "full_screen":
            continue

        color = ROI_COLORS.get(name, DEFAULT_COLOR)

        # 사각형
        cv2.rectangle(
            overlay,
            (region.x1, region.y1),
            (region.x2, region.y2),
            color, 2,
        )

        # 텍스트 배경 (가독성)
        label = f"{name} ({region.width}x{region.height})"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_x = region.x1
        label_y = region.y1 - 6 if region.y1 > 20 else region.y2 + 18

        # 텍스트 배경 박스
        cv2.rectangle(
            overlay,
            (label_x, label_y - th - 4),
            (label_x + tw + 4, label_y + 2),
            (0, 0, 0), -1,
        )
        # 텍스트
        cv2.putText(
            overlay, label,
            (label_x + 2, label_y - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"roi_overlay_{timestamp}.png"
    filepath = str(save_path / filename)
    cv2.imwrite(filepath, overlay)

    n_rois = len(names) - (1 if "full_screen" in names else 0)
    logger.info("ROI overlay saved: %s (%d ROIs)", filepath, n_rois)
    return filepath


def create_contact_sheet(
    crops: Dict[str, np.ndarray],
    save_dir: str | Path = "debug/contact_sheet",
    max_cols: int = 4,
    thumb_width: int = 320,
) -> str:
    """모든 ROI crop 결과를 한 장의 contact sheet로 합쳐 저장.

    Args:
        crops: {name: cropped_image} 딕셔너리
        save_dir: 저장 디렉터리
        max_cols: 한 줄 최대 컬럼 수
        thumb_width: 각 썸네일 너비 (px)

    Returns:
        저장된 파일 경로
    """
    if not crops:
        logger.warning("No crops to create contact sheet")
        return ""

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # crops를 행/열로 배치
    items = [(name, img) for name, img in crops.items() if img is not None]
    n_items = len(items)
    n_cols = min(max_cols, n_items)
    n_rows = (n_items + n_cols - 1) // n_cols

    # 각 썸네일 크기 계산
    label_height = 28
    thumb_height = thumb_width // 2  # 16:9 비율

    # 라벨 포함 썸네일 높이
    cell_h = thumb_height + label_height
    cell_w = thumb_width + 20  # 좌우 여백

    canvas_w = n_cols * cell_w + 20
    canvas_h = n_rows * cell_h + 20

    canvas = np.full((canvas_h, canvas_w, 3), 48, dtype=np.uint8)

    for idx, (name, img) in enumerate(items):
        row = idx // n_cols
        col = idx % n_cols

        # 이미지 resize (비율 유지)
        h, w = img.shape[:2]
        aspect = w / h
        if aspect > (thumb_width / thumb_height):
            # 너비 기준
            resized_w = thumb_width
            resized_h = int(thumb_width / aspect)
        else:
            # 높이 기준
            resized_h = thumb_height
            resized_w = int(thumb_height * aspect)

        thumb = cv2.resize(img, (resized_w, resized_h))

        # 캔버스에 배치 (중앙 정렬)
        x_off = col * cell_w + 10 + (thumb_width - resized_w) // 2
        y_off = row * cell_h + 10
        canvas[y_off:y_off + resized_h, x_off:x_off + resized_w] = thumb

        # ROI 이름 라벨
        label_y = y_off + resized_h + 20
        cv2.putText(
            canvas, name,
            (x_off, label_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (200, 200, 200), 1, cv2.LINE_AA,
        )

    # 상단 타이틀
    cv2.putText(
        canvas, f"ROI Contact Sheet — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        (10, 16),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"contact_sheet_{timestamp}.png"
    filepath = str(save_path / filename)
    cv2.imwrite(filepath, canvas)

    logger.info("Contact sheet saved: %s (%d ROIs, %dx%d grid)",
                filepath, n_items, n_cols, n_rows)
    return filepath
