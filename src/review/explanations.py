"""Deterministic, observation-only Korean explanations."""

from __future__ import annotations

from typing import Protocol

from src.review.models import FrameAnalysisRecord, SceneType
from src.state.models import GameStateSnapshot, Observation, ObservationStatus
from src.video_ingest.labels import ViewTarget


class ExplanationGenerator(Protocol):
    name: str

    def generate(self, record: FrameAnalysisRecord) -> str | None: ...


_SCENES = {
    SceneType.PLANNING: "준비 단계",
    SceneType.COMBAT: "전투 단계",
    SceneType.CAROUSEL: "공동 선택 단계",
    SceneType.AUGMENT_SELECT: "증강 선택 화면",
    SceneType.ITEM_SELECT: "아이템 선택 화면",
    SceneType.LOADING: "로딩 화면",
}

_VIEWS = {
    ViewTarget.SELF: "자신의 화면을 보고 있습니다.",
    ViewTarget.ENEMY: "상대 플레이어의 화면을 보고 있습니다.",
    ViewTarget.CAROUSEL: "공동 선택 화면을 보고 있습니다.",
}


def _observed(observation: Observation[object]) -> object | None:
    return observation.value if observation.status == ObservationStatus.OBSERVED else None


class TemplateExplanationGenerator:
    """Generate text without guessing values that recognizers did not observe."""

    name = "deterministic-template-v1"

    def generate(self, record: FrameAnalysisRecord) -> str | None:
        facts: list[str] = []
        minutes, seconds = divmod(record.timestamp_ms // 1000, 60)
        facts.append(f"{minutes}분 {seconds:02d}초")
        if record.scene_type in _SCENES:
            facts.append(f"{_SCENES[record.scene_type]}로 확인됩니다.")
        else:
            facts.append("현재 화면 종류는 확인 불가입니다.")
        facts.append(_VIEWS.get(record.view_target, "관전 대상은 확인 불가입니다."))
        if record.target_player:
            facts.append(f"대상 플레이어는 {record.target_player}입니다.")
        facts.extend(self._state_facts(record.state))
        return " ".join(facts)

    @staticmethod
    def _state_facts(state: GameStateSnapshot | None) -> list[str]:
        if state is None:
            return ["구조화된 게임 상태는 미인식입니다."]
        facts: list[str] = []
        gold = _observed(state.player_gold)
        level = _observed(state.player_level)
        stage = _observed(state.stage_info)
        facts.append(f"골드는 {gold}로 인식됐습니다." if gold is not None else "골드는 확인 불가입니다.")
        facts.append(f"레벨은 {level}로 인식됐습니다." if level is not None else "레벨은 확인 불가입니다.")
        facts.append(f"스테이지는 {stage}로 인식됐습니다." if stage is not None else "스테이지는 확인 불가입니다.")
        observed_shop = sum(item.status == ObservationStatus.OBSERVED for item in state.shop_slots)
        if observed_shop:
            facts.append(f"상점 {observed_shop}개 슬롯이 인식됐습니다.")
        board = state.enemy_board if state.metadata.get("view_target") == "enemy" else state.my_board
        if board.status != ObservationStatus.OBSERVED:
            facts.append("보드 상태는 미인식입니다.")
        return facts
