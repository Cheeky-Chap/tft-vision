"""
TFT Vision — Game Region Crop (MVP 1).

전체 모니터 캡처에서 TFT 게임 창 영역만 1차 crop.
2차 ROI crop은 이 game frame을 기준으로 실행.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("tft-vision.game_region")


class GameRegionCropError(Exception):
    """Game region crop 실패."""


class GameRegionCropper:
    """게임 영역 crop 관리자.

    모니터 전체 캡처에서 실제 게임 창 영역만 추출.
    2560x1440 모니터에서 1920x1080 테두리 없는 창모드 게임을 캡처하는 경우 등에 사용.

    Args:
        left: 게임 영역 좌측 x 좌표 (모니터 기준 절대 좌표)
        top: 게임 영역 상단 y 좌표
        width: 게임 영역 너비
        height: 게임 영역 높이
        save_dir: game frame 저장 디렉터리
    """

    def __init__(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        save_dir: str | Path = "captures/game",
    ):
        if width <= 0 or height <= 0:
            raise GameRegionCropError(
                f"Invalid game region size: {width}x{height}"
            )

        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "GameRegion initialized | region=(%d,%d) %dx%d save=%s",
            left, top, width, height, self.save_dir,
        )

    def crop(self, image: np.ndarray) -> np.ndarray:
        """전체 화면에서 게임 영역 crop.

        Args:
            image: 전체 모니터 캡처 (numpy array, HWC BGR)

        Returns:
            게임 영역만 crop된 이미지

        Raises:
            GameRegionCropError: 영역이 모니터 범위를 벗어난 경우
        """
        h, w = image.shape[:2]
        x2 = self.left + self.width
        y2 = self.top + self.height

        if x2 > w or y2 > h:
            raise GameRegionCropError(
                f"Game region ({self.left},{self.top},{self.width},{self.height}) "
                f"exceeds monitor bounds {w}x{h}. "
                f"Check MONITOR_INDEX or --monitor setting."
            )

        return image[self.top:y2, self.left:x2]

    def crop_and_save(
        self, image: np.ndarray
    ) -> tuple[np.ndarray, str]:
        """Crop + 저장.

        Args:
            image: 전체 모니터 캡처

        Returns:
            (game_frame_array, filepath)
        """
        game = self.crop(image)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}.png"
        filepath = str(self.save_dir / filename)
        cv2.imwrite(filepath, game)
        logger.debug(
            "Game frame saved: %s (%dx%d)",
            filename, game.shape[1], game.shape[0],
        )
        return game, filepath

    @staticmethod
    def parse_region(value: str) -> tuple[int, int, int, int]:
        """'LEFT,TOP,WIDTH,HEIGHT' 문자열을 파싱.

        Args:
            value: "320,180,1920,1080" 형식 문자열

        Returns:
            (left, top, width, height) 튜플
        """
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != 4:
            raise GameRegionCropError(
                f"Invalid game region format: '{value}'. "
                f"Expected: LEFT,TOP,WIDTH,HEIGHT (e.g. 320,180,1920,1080)"
            )
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            raise GameRegionCropError(
                f"Invalid game region values: '{value}'. "
                f"All values must be integers."
            )

    @staticmethod
    def load_from_env() -> Optional[tuple[int, int, int, int]]:
        """.env의 GAME_REGION_LEFT/TOP/WIDTH/HEIGHT를 읽어서 반환.

        Returns:
            (left, top, width, height) 또는 None (설정 안 됨)
        """
        import os

        try:
            left = int(os.environ.get("GAME_REGION_LEFT", ""))
            top = int(os.environ.get("GAME_REGION_TOP", ""))
            width = int(os.environ.get("GAME_REGION_WIDTH", ""))
            height = int(os.environ.get("GAME_REGION_HEIGHT", ""))
        except (ValueError, TypeError):
            return None

        if width <= 0 or height <= 0:
            return None

        return (left, top, width, height)
