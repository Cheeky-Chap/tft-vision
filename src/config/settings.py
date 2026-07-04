"""
TFT Vision — 설정 모듈.

환경변수(.env) + 기본 설정 관리.
MVP 1: 1920x1080 해상도 기준 하드코딩된 ROI.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class CaptureSettings:
    """캡처 관련 설정."""

    # 모니터/디스플레이
    monitor_index: int = 1            # 1 = 첫 번째 모니터, 2 = 두 번째, 0 = 전체 가상 데스크톱
    target_resolution: tuple = (1920, 1080)

    # 캡처 간격 (초)
    capture_interval: float = 1.0     # 일반 상태
    battle_capture_interval: float = 0.3  # 전투 중 빠른 캡처

    # 저장
    save_original: bool = True
    save_crops: bool = True
    crop_format: str = "png"

    # 디버그
    show_preview: bool = False        # ROI crop 결과 창 표시
    log_level: str = "INFO"


@dataclass
class ROIConfig:
    """ROI 영역 정의.
    모든 좌표는 (x1, y1, x2, y2) = (left, top, right, bottom).
    1920x1080 해상도 기준.
    """

    # 내 보드 영역 (체스판 8x7 그리드)
    my_board: tuple = (320, 240, 1600, 680)

    # 상점 (하단)
    shop: tuple = (360, 940, 1560, 1020)

    # 벤치 (상점 바로 위)
    bench: tuple = (320, 880, 1600, 940)

    # 아이템 조합대
    item_bench: tuple = (120, 880, 320, 1020)

    # 내 정보 (좌측 상단)
    player_info: tuple = (20, 20, 260, 120)

    # 라운드/스테이지 정보 (중앙 상단)
    stage_info: tuple = (800, 10, 1120, 60)

    # 상대 목록 (우측)
    opponent_list: tuple = (1640, 100, 1900, 980)

    # 증강 선택 (게임 시작/중간)
    augment_choice: tuple = (200, 300, 1720, 800)

    # 캐러셀 (중앙)
    carousel: tuple = (200, 200, 1720, 880)


@dataclass
class GameRegionConfig:
    """게임 영역 설정.

    전체 모니터 캡처에서 실제 TFT 게임 창 영역만 crop할 때 사용.
    2560x1440 모니터에서 1920x1080 테두리 없는 창모드 게임:
        left=320, top=180, width=1920, height=1080
    """
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0

    @property
    def enabled(self) -> bool:
        return self.width > 0 and self.height > 0
