"""
TFT Vision — 화면 캡처 모듈 (MVP 1).

Windows 전용. pyautogui + mss 백엔드로 TFT 화면 캡처.
AI-SERVER(Linux)에서는 동작하지 않음 (import 시 경고).
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("tft-vision.capture")

# Windows 전용 임포트 — 다른 플랫폼에서는 graceful fallback
_WINDOWS = False
try:
    import mss
    import pyautogui

    _WINDOWS = True
except ImportError:
    logger.warning(
        "pyautogui/mss not available — screen capture disabled. "
        "Run on Windows with: pip install -r requirements.txt"
    )


class ScreenCaptureError(Exception):
    """캡처 실패."""


class ScreenCapture:
    """화면 캡처 관리자.

    Args:
        monitor_index: 캡처할 모니터 번호 (1=주모니터)
        save_dir: 원본 캡처 저장 디렉터리
    """

    def __init__(
        self,
        monitor_index: int = 1,
        save_dir: str | Path = "captures",
    ):
        if not _WINDOWS:
            raise ScreenCaptureError(
                "ScreenCapture requires Windows + pyautogui/mss. "
                "Install requirements on your Windows machine."
            )

        self.monitor_index = monitor_index
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._sct = mss.mss()
        info = self._get_monitor_info()
        logger.info(
            "ScreenCapture initialized | monitor=%d left=%d top=%d %dx%d save=%s",
            info["index"],
            info["left"],
            info["top"],
            info["width"],
            info["height"],
            self.save_dir,
        )

    @staticmethod
    def list_monitors() -> list[dict]:
        """사용 가능한 모니터 목록 반환.

        Returns:
            [ {index, left, top, width, height, name}, ... ]
            index 0 = 전체 가상 데스크톱 (all monitors combined)
            index 1 = 첫 번째 모니터
            index 2 = 두 번째 모니터 ...
        """
        import mss as _mss

        monitors = []
        with _mss.mss() as sct:
            for i, m in enumerate(sct.monitors):
                monitors.append({
                    "index": i,
                    "left": m["left"],
                    "top": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                    "name": f"Monitor {i}" if i > 0 else "Virtual Desktop (all)",
                })
        return monitors

    def _get_monitor_info(self) -> dict:
        """현재 선택된 모니터의 정보."""
        monitor = self._sct.monitors[self.monitor_index]
        return {
            "index": self.monitor_index,
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"],
        }

    def capture(self) -> np.ndarray:
        """전체 화면 캡처 → numpy array (H, W, BGR)."""
        monitor = self._sct.monitors[self.monitor_index]
        screenshot = self._sct.grab(monitor)
        return np.asarray(screenshot)[:, :, :3]  # BGRA → BGR

    def capture_and_save(self) -> tuple[np.ndarray, str]:
        """캡처 + 저장. (image, filepath) 반환."""
        img = self.capture()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}.png"
        filepath = str(self.save_dir / filename)

        import cv2

        cv2.imwrite(filepath, img)
        logger.debug("Captured: %s (%dx%d)", filename, img.shape[1], img.shape[0])
        return img, filepath

    def release(self):
        """리소스 정리."""
        if hasattr(self, "_sct"):
            self._sct.close()
