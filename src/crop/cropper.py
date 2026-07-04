"""
TFT Vision — ROI Crop 모듈 (MVP 1).

전체 화면 캡처에서 정의된 ROI 영역을 추출/저장.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from src.crop.roi_definitions import ROI_REGIONS, Region

logger = logging.getLogger("tft-vision.crop")


class CropError(Exception):
    """Crop 실패."""


class ROICropper:
    """ROI crop 관리자.

    Args:
        base_dir: crops 저장 루트 디렉터리
        regions: 사용할 ROI 목록 (None = 전체)
    """

    def __init__(
        self,
        base_dir: str | Path = "crops",
        regions: Optional[list[str]] = None,
    ):
        self.base_dir = Path(base_dir)
        self.regions = regions or list(ROI_REGIONS.keys())

        # ROI별 저장 디렉터리 생성
        for name in self.regions:
            (self.base_dir / name).mkdir(parents=True, exist_ok=True)

        logger.info(
            "ROICropper initialized | %d regions dir=%s",
            len(self.regions),
            self.base_dir,
        )

    def crop_all(self, image: np.ndarray) -> dict[str, np.ndarray]:
        """전체 ROI crop → {name: cropped_image}."""
        results = {}
        for name in self.regions:
            try:
                region = ROI_REGIONS[name]
                crop = self._crop_region(image, region)
                results[name] = crop
            except Exception as e:
                logger.warning("Crop failed for '%s': %s", name, e)
        return results

    def crop_and_save(
        self, image: np.ndarray
    ) -> dict[str, str]:
        """Crop + 저장 → {name: filepath}."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        results = {}

        for name in self.regions:
            try:
                region = ROI_REGIONS[name]
                crop = self._crop_region(image, region)
                out_dir = self.base_dir / name
                out_dir.mkdir(parents=True, exist_ok=True)
                filepath = str(out_dir / f"{timestamp}.png")
                cv2.imwrite(filepath, crop)
                results[name] = filepath
                logger.debug("Saved crop: %s", filepath)
            except Exception as e:
                logger.warning("Crop+save failed for '%s': %s", name, e)

        return results

    def _crop_region(self, image: np.ndarray, region: Region) -> np.ndarray:
        """단일 ROI crop."""
        x1, y1, x2, y2 = region.box
        h, w = image.shape[:2]

        # 경계 검사
        if x1 < 0 or y1 < 0 or x2 > w or y2 > h:
            raise CropError(
                f"ROI {region.name} ({x1},{y1})-({x2},{y2}) "
                f"out of bounds for image {w}x{h}"
            )

        return image[y1:y2, x1:x2]
