from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class InteractiveStage(StrEnum):
    INTERCITY = "awaiting_intercity_selection"
    HOTEL = "awaiting_hotel_selection"
    ATTRACTIONS = "awaiting_attraction_selection"
    COMPLETE = "complete"


class InteractiveState(BaseModel):
    stage: InteractiveStage
    valid_option_ids: list[str]
    selections: dict[str, list[str]] = Field(default_factory=dict)


class InteractiveSession:
    def __init__(self, workspace: Path, state: InteractiveState) -> None:
        self.workspace = workspace
        self.state = state

    @property
    def path(self) -> Path:
        return self.workspace / "interactive-state.json"

    @classmethod
    def create(
        cls,
        workspace: Path,
        *,
        option_ids: list[str],
    ) -> InteractiveSession:
        workspace.mkdir(parents=True, exist_ok=True)
        session = cls(
            workspace,
            InteractiveState(
                stage=InteractiveStage.INTERCITY,
                valid_option_ids=option_ids,
            ),
        )
        session._save()
        return session

    @classmethod
    def load(cls, workspace: Path) -> InteractiveSession:
        state = InteractiveState.model_validate_json(
            (workspace / "interactive-state.json").read_text(encoding="utf-8")
        )
        return cls(workspace, state)

    def resume(
        self,
        *,
        selection_ids: list[str],
        next_option_ids: list[str],
    ) -> None:
        invalid = set(selection_ids) - set(self.state.valid_option_ids)
        if invalid:
            raise ValueError(f"selection was not offered: {sorted(invalid)}")
        self.state.selections[self.state.stage.value] = selection_ids
        next_stage = {
            InteractiveStage.INTERCITY: InteractiveStage.HOTEL,
            InteractiveStage.HOTEL: InteractiveStage.ATTRACTIONS,
            InteractiveStage.ATTRACTIONS: InteractiveStage.COMPLETE,
        }.get(self.state.stage, InteractiveStage.COMPLETE)
        self.state.stage = next_stage
        self.state.valid_option_ids = next_option_ids
        self._save()

    def _save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            self.state.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
