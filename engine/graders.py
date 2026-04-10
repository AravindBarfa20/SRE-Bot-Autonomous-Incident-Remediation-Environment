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


# ── Reward constants — ALL values keep final reward strictly inside (0.0, 1.0).
# The evaluator rejects exactly 0.0 and exactly 1.0.
STEP_COST             = 0.03   # per-step overhead
TRIAGE_REWARD         = 0.08   # bonus for identifying root cause
DESTRUCTIVE_PENALTY   = 0.20   # penalty for hitting a healthy service
RESOLUTION_REWARD     = 0.70   # terminal success reward (must keep sum < 1.0)
INVALID_ACTION_REWARD = 0.02   # positive floor for invalid actions
INVALID_ACTION_COST   = 0.10
PREMATURE_REWARD      = 0.02   # positive floor for premature resolve
PREMATURE_COST        = 0.15


def _clamp(value: float) -> float:
    """Hard boundary: reward must be strictly between 0 and 1."""
    return max(0.01, min(0.99, float(value)))


def calculate_reward(context: RewardContext) -> RewardBreakdown:
    # 1. TERMINAL: Invalid action
    # OLD: reward=-0.05 → negative → REJECTED by evaluator
    if context.invalid_action:
        return RewardBreakdown(
            reward=_clamp(INVALID_ACTION_REWARD),
            incident_cost_delta=_clamp(INVALID_ACTION_COST),
            error=context.invalid_reason or "Invalid action format",
        )

    # 2. TERMINAL: Premature resolve
    # OLD: reward=-1.0, cost=1.0 → BOTH boundary violations
    if context.premature_resolve:
        return RewardBreakdown(
            reward=_clamp(PREMATURE_REWARD),
            incident_cost_delta=_clamp(PREMATURE_COST),
            error="Resolve called before the incident was verified as healthy",
        )

    # 3. INTERMEDIATE step reward — starts positive, never goes negative
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

    # 4. TERMINAL: Successful resolve
    # OLD: RESOLUTION_REWARD=1.0 → could push reward to exactly 1.0
    if context.successful_resolve:
        reward += RESOLUTION_REWARD

    return RewardBreakdown(
        reward=_clamp(reward),
        incident_cost_delta=_clamp(incident_cost_delta),
        root_cause_identified=context.triage_milestone_awarded,
        unnecessary_action=destructive,
        resolution_verified=context.successful_resolve,
    )        return RewardBreakdown(
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
