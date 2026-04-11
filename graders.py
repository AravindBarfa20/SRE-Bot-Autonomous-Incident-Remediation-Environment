from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.models import Action, ActionType, RewardBreakdown

__all__ = ["RewardContext", "calculate_reward"]

_REWARD_MIN = 0.001
_REWARD_MAX = 0.990
_FAILURE_REWARD = _REWARD_MIN

_STEP_COST              = 0.001
_BASE_STEP_REWARD       = 0.001
_TRIAGE_REWARD          = 0.005
_DESTRUCTIVE_PENALTY    = 0.050
_RESOLUTION_REWARD      = 0.500
_INVALID_ACTION_COST    = 0.005
_PREMATURE_RESOLVE_COST = 0.010


def _clamp_reward(raw: float) -> float:
    return round(max(_REWARD_MIN, min(_REWARD_MAX, float(raw))), 3)


def _clamp_cost(raw: float) -> float:
    return round(max(0.0, float(raw)), 3)


@dataclass(frozen=True)
class RewardContext:
    action: Action
    target_health_score: int
    triage_milestone_awarded: bool = False
    successful_resolve: bool = False
    premature_resolve: bool = False
    invalid_action: bool = False
    is_destructive_action: bool = False
    invalid_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0 <= self.target_health_score <= 100):
            raise ValueError(f"target_health_score must be in [0, 100], got {self.target_health_score}")
        if self.successful_resolve and self.premature_resolve:
            raise ValueError("successful_resolve and premature_resolve cannot both be True")
        if self.successful_resolve and self.invalid_action:
            raise ValueError("successful_resolve and invalid_action cannot both be True")


def calculate_reward(context: RewardContext) -> RewardBreakdown:
    if context.invalid_action:
        return RewardBreakdown(
            reward=_FAILURE_REWARD,
            incident_cost_delta=_clamp_cost(_INVALID_ACTION_COST),
            error=context.invalid_reason or "Invalid action format",
            root_cause_identified=False,
            unnecessary_action=False,
            resolution_verified=False,
        )

    if context.premature_resolve:
        return RewardBreakdown(
            reward=_FAILURE_REWARD,
            incident_cost_delta=_clamp_cost(_PREMATURE_RESOLVE_COST),
            error="Resolve called before the incident was verified as healthy",
            root_cause_identified=context.triage_milestone_awarded,
            unnecessary_action=False,
            resolution_verified=False,
        )

    reward: float = _BASE_STEP_REWARD
    incident_cost_delta: float = _STEP_COST

    if context.triage_milestone_awarded:
        reward += _TRIAGE_REWARD

    if context.is_destructive_action:
        reward = max(_REWARD_MIN, reward - _DESTRUCTIVE_PENALTY)
        incident_cost_delta += _DESTRUCTIVE_PENALTY

    if context.successful_resolve:
        reward += _RESOLUTION_REWARD

    return RewardBreakdown(
        reward=_clamp_reward(reward),
        incident_cost_delta=_clamp_cost(incident_cost_delta),
        root_cause_identified=context.triage_milestone_awarded,
        unnecessary_action=context.is_destructive_action,
        resolution_verified=context.successful_resolve,
    )
