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


STEP_COST = 0.05
TRIAGE_REWARD = 0.1
DESTRUCTIVE_PENALTY = 0.5
RESOLUTION_REWARD = 1.0
INVALID_ACTION_PENALTY = 0.05


def calculate_reward(context: RewardContext) -> RewardBreakdown:
    if context.invalid_action:
        return RewardBreakdown(
            reward=-INVALID_ACTION_PENALTY,
            incident_cost_delta=INVALID_ACTION_PENALTY,
            error=context.invalid_reason or "Invalid action format",
        )

    if context.premature_resolve:
        return RewardBreakdown(
            reward=-1.0,
            incident_cost_delta=1.0,
            error="Resolve called before the incident was verified as healthy",
        )

    reward = -STEP_COST
    incident_cost_delta = STEP_COST

    if context.triage_milestone_awarded:
        reward += TRIAGE_REWARD

    destructive = (
        context.action.action_type in {ActionType.RESTART_SERVICE, ActionType.ROLLBACK_CONFIG}
        and context.target_health_score >= 100
    )
    if destructive:
        reward -= DESTRUCTIVE_PENALTY
        incident_cost_delta += DESTRUCTIVE_PENALTY

    if context.successful_resolve:
        reward += RESOLUTION_REWARD

    return RewardBreakdown(
        reward=reward,
        incident_cost_delta=incident_cost_delta,
        root_cause_identified=context.triage_milestone_awarded,
        unnecessary_action=destructive,
        resolution_verified=context.successful_resolve,
    )
