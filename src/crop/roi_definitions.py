"""
ROI 영역 정의 — 화면 영역별 식별자와 좌표.

1920x1080 해상도 TFT 기본 기준.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Region:
    """ROI 영역."""
    name: str
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def box(self) -> Tuple[int, int, int, int]:
        """PIL/cv2 호환 bounding box."""
        return (self.x1, self.y1, self.x2, self.y2)


# --- 기본 ROI 정의 (1920x1080) ---
ROI_REGIONS = {
    "my_board":       Region("my_board",       320, 240, 1600, 680),
    "shop":           Region("shop",           360, 940, 1560, 1020),
    "bench":          Region("bench",          320, 880, 1600, 940),
    "item_bench":     Region("item_bench",     120, 880,  320, 1020),
    "player_info":    Region("player_info",     20,  20,  260,  120),
    "stage_info":     Region("stage_info",     800,  10, 1120,   60),
    "opponent_list":  Region("opponent_list", 1640, 100, 1900,  980),
    "augment_choice": Region("augment_choice", 200, 300, 1720,  800),
    "carousel":       Region("carousel",       200, 200, 1720,  880),
    "full_screen":    Region("full_screen",      0,   0, 1920, 1080),
}


def list_roi_names() -> list:
    """정의된 ROI 이름 목록."""
    return list(ROI_REGIONS.keys())


def get_roi(name: str) -> Region:
    """이름으로 ROI 조회."""
    region = ROI_REGIONS.get(name)
    if not region:
        raise KeyError(f"Unknown ROI: {name}. Available: {list_roi_names()}")
    return region


def roi_for_display(name: str) -> str:
    """ROI 설명."""
    r = get_roi(name)
    return f"{name}: ({r.x1},{r.y1})-({r.x2},{r.y2}) [{r.width}x{r.height}]"
