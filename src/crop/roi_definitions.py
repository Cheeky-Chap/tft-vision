"""
ROI 영역 정의 — 화면 영역별 식별자와 좌표.

1920x1080 game frame 기준.
좌표는 실제 captures/game/*.png 이미지로 보정 완료.
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


# --- ROI 정의 (1920x1080 game frame 기준, captures/game 보정 완료) ---
ROI_REGIONS = {
    # ── 좌측 아이템/장비 영역 ──
    "item_area":      Region("item_area",        0, 270,  110, 780),

    # ── 플레이어 HUD (하단 정보) ──
    "player_level":   Region("player_level",   260, 870,  470, 920),
    "player_gold":    Region("player_gold",    910, 880, 1040, 920),
    "player_streak":  Region("player_streak", 1040, 870, 1120, 920),

    # ── 상점 ──
    "shop":           Region("shop",           470, 920, 1490, 1080),

    # ── 스테이지 정보 (상단 중앙) ──
    "stage_info":     Region("stage_info",     730,   0, 1180,  40),

    # ── 상대 목록 (우측) ──
    "player_list":    Region("player_list",   1620, 180, 1920, 800),

    # ── 상대 필드 ──
    "enemy_bench":    Region("enemy_bench",    550,  35, 1350, 170),
    "enemy_board":    Region("enemy_board",    520,  95, 1380, 410),

    # ── 내 필드 ──
    "my_board":       Region("my_board",       450, 330, 1460, 730),
    "my_bench":       Region("my_bench",       370, 680, 1460, 870),

    # ── 전체 ──
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
