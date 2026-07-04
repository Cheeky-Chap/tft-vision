"""
TFT Vision — Sample Collection (데이터 수집 모듈).

--sample-run 옵션으로 활성화.
세션별 폴더에 정리된 crop 샘플을 저장하여 향후 OCR/인식 학습 데이터로 활용.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import cv2
import numpy as np

logger = logging.getLogger("tft-vision.sample_collector")

# 샘플 수집 대상 ROI (OCR/인식 학습에 사용할 ROI 목록)
SAMPLE_ROIS = [
    "shop_slot_1",
    "shop_slot_2",
    "shop_slot_3",
    "shop_slot_4",
    "shop_slot_5",
    "player_gold",
    "player_level",
    "stage_info",
    "my_board",
    "my_bench",
]


class SampleCollector:
    """샘플 수집 관리자.

    세션별 폴더를 생성하고 game frame + ROI crop을 정리하여 저장.
    """

    def __init__(self, base_dir: str | Path = "samples"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = Path(base_dir) / f"session_{timestamp}"
        self.capture_count = 0

        # 세션 폴더 생성
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # game frame 저장 폴더
        self.game_dir = self.session_dir / "game"
        self.game_dir.mkdir(exist_ok=True)

        # ROI별 저장 폴더
        self.roi_dirs: dict[str, Path] = {}
        for name in SAMPLE_ROIS:
            d = self.session_dir / name
            d.mkdir(exist_ok=True)
            self.roi_dirs[name] = d

        logger.info(
            "Sample session started: %s (%d ROIs)",
            self.session_dir, len(SAMPLE_ROIS),
        )

    @property
    def session_name(self) -> str:
        return self.session_dir.name

    @property
    def session_path(self) -> Path:
        return self.session_dir

    def collect(
        self,
        game_frame: np.ndarray,
        crops: Dict[str, np.ndarray],
        frame_idx: int,
    ) -> dict[str, str]:
        """한 프레임의 샘플을 수집.

        Args:
            game_frame: game frame (numpy array)
            crops: {roi_name: cropped_image} 전체 ROI crop 결과
            frame_idx: 현재 프레임 인덱스 (1-based)

        Returns:
            {name: saved_filepath} 딕셔너리
        """
        self.capture_count += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        saved: dict[str, str] = {}

        # Game frame 저장
        game_filename = f"{ts}_{frame_idx:04d}.png"
        game_path = str(self.game_dir / game_filename)
        cv2.imwrite(game_path, game_frame)
        saved["game"] = game_path
        logger.debug("Sample game: %s", game_path)

        # ROI crop 저장 (지정된 ROI만)
        for name in SAMPLE_ROIS:
            crop_img = crops.get(name)
            if crop_img is None:
                continue
            roi_filename = f"{ts}_{frame_idx:04d}.png"
            roi_path = str(self.roi_dirs[name] / roi_filename)
            cv2.imwrite(roi_path, crop_img)
            saved[name] = roi_path

        logger.debug(
            "Sample [%d] collected: game + %d ROIs", self.capture_count, len(saved) - 1,
        )
        return saved
