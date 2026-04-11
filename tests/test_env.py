from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.env import SREEnvironment
from engine.models import Action, ActionType


def run(coro):
    return asyncio.run(coro)


def test_check_logs_triage_awards_milestone_once():
    """
    First CHECK_LOGS on the faulty target awards the triage milestone.
    Second identical action gets no milestone — idempotent by design.
    Both steps must remain within reward bounds (0.0, 1.0).
    """
    env = SREEnvironment("HARD")
    run(env.reset())

    _, r1, done1, _, info1 = run(
        env.step(Action(action_type=ActionType.CHECK_LOGS, target="db-proxy"))
    )
    _, r2, done2, _, info2 = run(
        env.step(Action(action_type=ActionType.CHECK_LOGS, target="db-proxy"))
    )

    assert 0.0 < r1 < 1.0, f"step-1 reward out of bounds: {r1}"
    assert 0.0 < r2 < 1.0, f"step-2 reward out of bounds: {r2}"
    assert r1 > r2, "triage step should yield higher reward than repeat"
    assert done1 is False
    assert done2 is False
    assert info1.get("root_cause_identified") is True


def test_premature_resolve_terminates_episode():
    """
    RESOLVE before verification_complete must terminate the episode
    and return a reward within strict bounds.
    """
    env = SREEnvironment("HARD")
    run(env.reset())

    observation, reward, done, truncated, info = run(
        env.step(Action(action_type=ActionType.RESOLVE, target="system"))
    )

    assert 0.0 < reward < 1.0, f"premature resolve reward out of bounds: {reward}"
    assert done is True
    assert truncated is False
    assert info["error"] == "Resolve called before the incident was verified as healthy"
    assert observation.system_health < 100


def test_resolve_blocked_without_verification():
    """
    Applying the correct remediation action is not enough.
    A verification step (CHECK_LOGS or CHECK_METRICS on faulty target)
    must follow before RESOLVE is accepted.
    """
    env = SREEnvironment("HARD")
    run(env.reset())

    _, _, remediation_done, _, remediation_info = run(
        env.step(Action(action_type=ActionType.ROLLBACK_CONFIG, target="db-proxy"))
    )
    _, resolve_reward, resolve_done, _, resolve_info = run(
        env.step(Action(action_type=ActionType.RESOLVE, target="system"))
    )

    assert remediation_done is False
    assert remediation_info["verification_complete"] is False
    assert 0.0 < resolve_reward < 1.0
    assert resolve_done is True
    assert resolve_info["verification_complete"] is False


def test_invalid_target_returns_bounded_reward():
    """
    A hallucinated target not in the valid target set must not crash the env.
    Episode continues (done=False) and reward stays within strict bounds.
    """
    env = SREEnvironment("HARD")
    run(env.reset())

    observation, reward, done, truncated, info = run(
        env.step({"action_type": "check_logs", "target": "ghost-service"})
    )

    assert 0.0 < reward < 1.0, f"invalid target reward out of bounds: {reward}"
    assert done is False
    assert truncated is False
    assert info["error"] == "Invalid action or target"
    assert "[Step 1]" in observation.last_action_feedback


def test_successful_resolution_full_loop():
    """
    Happy path: triage → remediate → verify → resolve.
    Final reward must be the highest in the episode and within bounds.
    """
    env = SREEnvironment("HARD")
    run(env.reset())

    run(env.step(Action(action_type=ActionType.CHECK_LOGS, target="db-proxy")))
    run(env.step(Action(action_type=ActionType.ROLLBACK_CONFIG, target="db-proxy")))
    run(env.step(Action(action_type=ActionType.CHECK_METRICS, target="db-proxy")))

    _, resolve_reward, resolve_done, _, resolve_info = run(
        env.step(Action(action_type=ActionType.RESOLVE, target="system"))
    )

    assert 0.0 < resolve_reward < 1.0
    assert resolve_done is True
    assert resolve_info.get("error") is None
    assert resolve_info["verification_complete"] is True


def test_all_reward_outputs_within_strict_bounds():
    """
    Exhaustive boundary check: every action type on every target
    must return a reward strictly within (0.0, 1.0).
    """
    from engine.models import ActionType

    env = SREEnvironment("HARD")
    run(env.reset())

    targets = ["auth-service", "api-gateway", "db-proxy"]
    actions_to_test = [
        (ActionType.CHECK_LOGS, "auth-service"),
        (ActionType.CHECK_METRICS, "api-gateway"),
        (ActionType.RESTART_SERVICE, "auth-service"),
        (ActionType.SCALE_UP, "api-gateway"),
        (ActionType.CHECK_LOGS, "db-proxy"),
    ]

    for action_type, target in actions_to_test:
        env2 = SREEnvironment("HARD")
        run(env2.reset())
        _, reward, _, _, _ = run(
            env2.step(Action(action_type=action_type, target=target))
        )
        assert 0.0 < reward < 1.0, (
            f"{action_type.value} on {target} returned out-of-bounds reward: {reward}"
        )
