from dataclasses import dataclass
from typing import Optional

try:
    from .models import Action, ActionType, RewardBreakdown
except ImportError:  # pragma: no cover - script fallback
    from models import Action, ActionType, RewardBreakdown


@dataclass(frozen=True)
class RewardContext:
    action: Action
    target_health_score: int
    triage_milestone_awarded: bool = False
    successful_resolve: bool = False
    premature_resolve: bool = False
    invalid_action: bool = False
    invalid_reason: Optional[str] = None


def calculate_reward(context: RewardContext) -> RewardBreakdown:
    
    if context.invalid_action or context.premature_resolve:
        return RewardBreakdown(
            reward=0.001,
            incident_cost_delta=0.005,  
            root_cause_identified=context.triage_milestone_awarded,
            unnecessary_action=True,
            resolution_verified=False,
            error=context.invalid_reason or "Terminal failure"
        )

    if context.successful_resolve:
        return RewardBreakdown(
            reward=0.500, 
            incident_cost_delta=0.001,
            root_cause_identified=context.triage_milestone_awarded,
            unnecessary_action=False,
            resolution_verified=True
        )

    # Normal intermediate step
    return RewardBreakdown(
        reward=0.001,
        incident_cost_delta=0.002, 
        root_cause_identified=context.triage_milestone_awarded,
        unnecessary_action=False,
        resolution_verified=False
    )
