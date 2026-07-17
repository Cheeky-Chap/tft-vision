"""Human-editable labels for extracted gameplay frames and selection events."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ViewTarget(str, Enum):
    SELF = "self"
    ENEMY = "enemy"
    CAROUSEL = "carousel"
    UNKNOWN = "unknown"


class Phase(str, Enum):
    PLANNING = "planning"
    COMBAT = "combat"
    CAROUSEL = "carousel"
    AUGMENT_SELECT = "augment_select"
    ITEM_SELECT = "item_select"
    POST_COMBAT = "post_combat"
    LOADING = "loading"
    UNKNOWN = "unknown"


class ScreenType(str, Enum):
    NORMAL_BOARD = "normal_board"
    AUGMENT_SELECT = "augment_select"
    ITEM_SELECT = "item_select"
    CAROUSEL = "carousel"
    LOADING = "loading"
    OTHER = "other"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    PLAYER_VIEW_CHANGED = "player_view_changed"
    AUGMENT_SELECTED = "augment_selected"
    CHAMPION_PURCHASED = "champion_purchased"
    CHAMPION_SOLD = "champion_sold"
    ITEM_SELECTED = "item_selected"
    ITEM_EQUIPPED = "item_equipped"
    SHOP_REFRESHED = "shop_refreshed"
    LEVEL_UP = "level_up"


class FrameLabel(BaseModel):
    frame_id: str
    view_target: ViewTarget = ViewTarget.UNKNOWN
    target_player: str | None = None
    phase: Phase = Phase.UNKNOWN
    screen_type: ScreenType = ScreenType.UNKNOWN
    shop_visible: bool | None = None
    board_visible: bool | None = None
    bench_visible: bool | None = None
    augment_options_visible: bool | None = None
    item_selection_visible: bool | None = None
    notes: str | None = None


class SelectionEvent(BaseModel):
    event_id: str
    event_type: EventType
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    before_frame_id: str | None = None
    after_frame_id: str | None = None
    selected_option: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "SelectionEvent":
        if self.end_ms < self.start_ms:
            raise ValueError("event end_ms must be greater than or equal to start_ms")
        return self


class VideoLabels(BaseModel):
    schema_version: str = "1.0"
    source_id: str
    frames: list[FrameLabel]
    events: list[SelectionEvent] = Field(default_factory=list)


def empty_labels(source_id: str, frame_ids: list[str]) -> VideoLabels:
    return VideoLabels(source_id=source_id, frames=[FrameLabel(frame_id=value) for value in frame_ids])
