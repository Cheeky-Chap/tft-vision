"""
ROI 영역 정의 — 화면 영역별 식별자와 좌표.

1920x1080 해상도 TFT 기본 기준 (game frame 기준).
실제 game frame 이미지로 좌표 보정 필요시 수정.

각 ROI는 단일 UI 정보 요소를 캡처하도록 설계.
player_hud 영역은 레벨/경험치/골드/체력/연승으로 세분화.
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


# --- 기본 ROI 정의 (1920x1080 game frame 기준) ---
# 좌표는 임시값 — captures/game 이미지로 직접 보정 필요
ROI_REGIONS = {
    # ── 플레이어 HUD (좌측 상단) ──
    # 레벨 (레벨 숫자 hexagon)
    "player_level":   Region("player_level",   20,  20,  70,  60),
    # 골드 (골드 아이콘 + 보유량)
    "player_gold":    Region("player_gold",    75,  20, 155,  60),
    # 체력 (HP 바 + 숫자)
    "player_hp":      Region("player_hp",     160,  20, 260,  60),
    # 경험치 XP 바 (레벨/골드 아래)
    "player_xp":      Region("player_xp",      20,  65, 260,  92),
    # 연승/연패 스트릭 표시
    "player_streak":  Region("player_streak",   20,  95, 260, 120),

    # ── 전체 HUD 디버깅용 (위 세분화 ROI를 포함하는 큰 영역) ──
    "player_hud_debug": Region("player_hud_debug", 20, 20, 260, 120),

    # ── 게임 필드 ──
    "my_board":       Region("my_board",       320, 240, 1600, 680),
    "bench":          Region("bench",          320, 880, 1600, 940),
    "item_bench":     Region("item_bench",     120, 880,  320, 1020),

    # ── 상점 ──
    "shop":           Region("shop",           360, 940, 1560, 1020),

    # ── 정보 ──
    "stage_info":     Region("stage_info",     800,  10, 1120,   60),
    "opponent_list":  Region("opponent_list", 1640, 100, 1900,  980),

    # ── 이벤트 ──
    "augment_choice": Region("augment_choice", 200, 300, 1720,  800),
    "carousel":       Region("carousel",       200, 200, 1720,  880),

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
