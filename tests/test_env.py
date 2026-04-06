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


def test_reward_idempotency_for_log_triage():
    env = SREEnvironment("HARD")
    run(env.reset())

    _, first_reward, first_done, _, _ = run(
        env.step(Action(action_type=ActionType.CHECK_LOGS, target="db-proxy"))
    )
    _, second_reward, second_done, _, _ = run(
        env.step(Action(action_type=ActionType.CHECK_LOGS, target="db-proxy"))
    )

    assert first_reward == 0.05
    assert second_reward == -0.05
    assert first_done is False
    assert second_done is False


def test_premature_resolve_applies_massive_penalty_and_terminates():
    env = SREEnvironment("HARD")
    run(env.reset())

    observation, reward, done, truncated, info = run(
        env.step(Action(action_type=ActionType.RESOLVE, target="system"))
    )

    assert reward == -1.0
    assert done is True
    assert truncated is False
    assert info["error"] == "Resolve called before the incident was verified as healthy"
    assert observation.system_health < 100


def test_verification_loop_blocks_resolve_after_fix_without_checks():
    env = SREEnvironment("HARD")
    run(env.reset())

    _, remediation_reward, remediation_done, _, remediation_info = run(
        env.step(Action(action_type=ActionType.ROLLBACK_CONFIG, target="db-proxy"))
    )
    observation, resolve_reward, resolve_done, _, resolve_info = run(
        env.step(Action(action_type=ActionType.RESOLVE, target="system"))
    )

    assert remediation_reward == -0.05
    assert remediation_done is False
    assert remediation_info["verification_complete"] is False
    assert resolve_reward == -1.0
    assert resolve_done is True
    assert resolve_info["verification_complete"] is False
    assert observation.last_action_feedback.startswith("[Step 2]")


def test_hallucinated_invalid_target_returns_observation_and_penalty():
    env = SREEnvironment("HARD")
    run(env.reset())

    observation, reward, done, truncated, info = run(
        env.step({"action_type": "check_logs", "target": "ghost-service"})
    )

    assert reward == -0.05
    assert done is False
    assert truncated is False
    assert info["error"] == "Invalid action or target"
    assert observation.last_action_feedback == "[Step 1] Error: Invalid action or target"
