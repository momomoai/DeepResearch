from typing import Dict, List, Any, Optional
from ..types import AnswerAction, ActionType

class ActionState:
    def __init__(self):
        self.this_step: AnswerAction = AnswerAction(
            action=ActionType.ANSWER,
            answer="",
            references=[],
            think=""
        )
        self.gaps: List[str] = []
        self.bad_attempts: int = 0
        self.total_step: int = 0

class ActionTracker:
    def __init__(self):
        self._state = ActionState()

    async def track_action(self, new_state: Dict[str, Any]) -> None:
        if "this_step" in new_state:
            self._state.this_step = new_state["this_step"]
        if "gaps" in new_state:
            self._state.gaps = new_state["gaps"]
        if "bad_attempts" in new_state:
            self._state.bad_attempts = new_state["bad_attempts"]
        if "total_step" in new_state:
            self._state.total_step = new_state["total_step"]

    def get_state(self) -> Dict[str, Any]:
        return {
            "this_step": self._state.this_step,
            "gaps": self._state.gaps,
            "bad_attempts": self._state.bad_attempts,
            "total_step": self._state.total_step
        }

    def reset(self) -> None:
        self._state = ActionState()
