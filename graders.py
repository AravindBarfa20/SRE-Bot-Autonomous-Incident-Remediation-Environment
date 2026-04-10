from dataclasses import dataclass
from typing import Optional

try:
    from engine.models import Action, ActionType, RewardBreakdown
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


STEP_COST             = 0.03
TRIAGE_REWARD         = 0.08
DESTRUCTIVE_PENALTY   = 0.20
RESOLUTION_REWARD     = 0.70
INVALID_ACTION_REWARD = 0.02
INVALID_ACTION_COST   = 0.10
PREMATURE_REWARD      = 0.02
PREMATURE_COST        = 0.15


def _clamp(value: float) -> float:
    """Hard boundary: reward must be strictly between 0 and 1."""
    return max(0.01, min(0.99, float(value)))


def calculate_reward(context: RewardContext) -> RewardBreakdown:
    if context.invalid_action:
        return RewardBreakdown(
            reward=_clamp(INVALID_ACTION_REWARD),
            incident_cost_delta=_clamp(INVALID_ACTION_COST),
            error=context.invalid_reason or "Invalid action format",
        )

    if context.premature_resolve:
        return RewardBreakdown(
            reward=_clamp(PREMATURE_REWARD),
            incident_cost_delta=_clamp(PREMATURE_COST),
            error="Resolve called before the incident was verified as healthy",
        )

    reward = 0.04
    incident_cost_delta = STEP_COST

    if context.triage_milestone_awarded:
        reward += TRIAGE_REWARD

    destructive = (
        context.action.action_type in {ActionType.RESTART_SERVICE, ActionType.ROLLBACK_CONFIG}
        and context.target_health_score >= 100
    )
    if destructive:
        reward = max(0.02, reward - DESTRUCTIVE_PENALTY)
        incident_cost_delta += DESTRUCTIVE_PENALTY

    if context.successful_resolve:
        reward += RESOLUTION_REWARD

    return RewardBreakdown(
        reward=_clamp(reward),
        incident_cost_delta=_clamp(incident_cost_delta),
        root_cause_identified=context.triage_milestone_awarded,
        unnecessary_action=destructive,
        resolution_verified=context.successful_resolve,
    )
