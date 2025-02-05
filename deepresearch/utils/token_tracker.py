import logging
from typing import Dict, List, Optional, Union
from openai.types.chat import ChatCompletion
from ..types import TokenUsage

class TokenTracker:
    def __init__(self, budget: Optional[int] = None):
        self.usages: List[TokenUsage] = []
        self.budget = budget

    async def track_usage(self, tool: str, usage: Union[ChatCompletion, int]) -> None:
        tokens = usage.usage.total_tokens if isinstance(usage, ChatCompletion) else usage

        current_total = self.get_total_usage()
        if self.budget and current_total + tokens > self.budget:
            logging.error(f"Token budget exceeded: {current_total + tokens} > {self.budget}")
            return

        if not self.budget or current_total + tokens <= self.budget:
            self.usages.append(TokenUsage(tool=tool, tokens=tokens))

    def get_total_usage(self) -> int:
        return sum(usage.tokens for usage in self.usages)

    def get_usage_breakdown(self) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        for usage in self.usages:
            breakdown[usage.tool] = breakdown.get(usage.tool, 0) + usage.tokens
        return breakdown

    def print_summary(self) -> None:
        breakdown = self.get_usage_breakdown()
        logging.info("Token Usage Summary: %s", {
            "total": self.get_total_usage(),
            "breakdown": breakdown
        })

    def reset(self) -> None:
        self.usages = []
