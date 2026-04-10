import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional
from openai import AsyncOpenAI
import openai


ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "engine"
for candidate in (str(ROOT), str(ENGINE_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from agent import VALID_TARGETS, HuggingFaceAgentError, HuggingFaceSREAgent
from env import IncidentEnv
from models import Action, ActionType


# ── Env-var configuration ─────────────────────────────────────────────────────
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str = os.getenv(
    "MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct"
)

MODEL_ALIASES: dict[str, str] = {
    "qwen-7b": MODEL_NAME,
    "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.3",
}

EPISODE_DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")
MAX_STEPS: int = 8
RETRY_DELAYS_SECONDS: tuple[int, ...] = (2, 4, 8)

# ── LLM defaults ─────────────────────────────────────────────────────────────
DEFAULT_TEMPERATURE: float = 0.0
DEFAULT_SEED: int = 42


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenEnv-compliant evaluation runner."
    )
    parser.add_argument(
        "--model",
        default="qwen-7b",
        choices=sorted(MODEL_ALIASES),
        help="Agent model alias to use for all benchmark tasks.",
    )
    return parser.parse_args()


def _build_agent(model_alias: str) -> HuggingFaceSREAgent:
    model_id = MODEL_ALIASES[model_alias]
    agent = HuggingFaceSREAgent(model_id=model_id)
    if not agent.is_configured():
        raise HuggingFaceAgentError(
            "Missing Hugging Face API token. Set HF_TOKEN environment variable."
        )
    print(
        f"[SYSTEM] Using model={model_id}",
        file=sys.stderr,
        flush=True,
    )
    return agent


def _normalize_error(value: Optional[str]) -> str:
    return value if value else "null"


# ── CRITICAL: Hard clamp — score MUST be strictly (0.0, 1.0) exclusive ────────
def _clamp_reward(value) -> float:
    """
    Guarantees the reward is strictly between 0 and 1.
    The evaluator rejects exactly 0.0 and exactly 1.0.
    Applied defensively at every point rewards are produced.
    """
    try:
        f = float(value)
    except (ValueError, TypeError):
        return 0.05  # safe fallback
    return max(0.01, min(0.99, f))


def _extract_json_candidate(text: str) -> str:
    """Robust regex-based JSON extraction from LLM response text."""
    # 1. Fenced code blocks: ```json\n{...}\n```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    # 2. Bare JSON object: {...}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    # 3. Fallback: first { to last } in the string
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise HuggingFaceAgentError(
        f"Model did not return a JSON object. Response: {text!r}"
    )


def _parse_action_from_text(model_text: str) -> Action:
    candidate = _extract_json_candidate(model_text)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise HuggingFaceAgentError(
            f"Model did not return valid JSON: {model_text!r}"
        ) from exc

    action_type = payload.get("action_type")
    target = payload.get("target")
    if action_type not in {member.value for member in ActionType}:
        raise HuggingFaceAgentError(
            f"Invalid action_type from model: {action_type!r}"
        )
    if target not in VALID_TARGETS:
        raise HuggingFaceAgentError(
            f"Invalid target from model: {target!r}"
        )

    return Action(
        action_type=ActionType(str(action_type)),
        target=str(target),
        rationale=str(payload.get("reasoning", "")).strip()
        or "No rationale provided by model.",
    )


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError, openai.InternalServerError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code in {429, 502, 503, 504}
    return False


async def _choose_action_with_retry(
    agent: HuggingFaceSREAgent, observation, step: int
) -> Action:
    if not agent.token:
        raise HuggingFaceAgentError(
            "Missing Hugging Face API token. Set HF_TOKEN."
        )

    prompt = agent._build_prompt(observation, step)
    client = AsyncOpenAI(api_key=agent.token, base_url=API_BASE_URL)

    last_error: Optional[Exception] = None
    max_attempts = len(RETRY_DELAYS_SECONDS) + 1

    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.chat.completions.create(
                model=agent.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=220,
                temperature=0.0,   # REQUIRED by evaluator
                seed=42,           # REQUIRED by evaluator
            )
            model_text = response.choices[0].message.content or ""
            return _parse_action_from_text(model_text)

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= max_attempts or not _is_retryable_error(exc):
                break

            delay = RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"[RETRY] attempt={attempt}/{max_attempts} "
                f"error={exc!s} delay={delay}s",
                file=sys.stderr,
                flush=True,
            )
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


async def _run_episode(difficulty: str, agent: HuggingFaceSREAgent) -> None:
    env = IncidentEnv(difficulty=difficulty)
    observation = await env.reset()
    rewards: List[str] = []
    success = False

    task_name = getattr(observation, 'task_name', 'incident-task')
    benchmark = getattr(observation, 'benchmark', 'sre-benchmark')

    print(
        f"[START] task={task_name} "
        f"env={benchmark} model={agent.model_id}",
        flush=True,
    )

    for step in range(1, MAX_STEPS + 1):
        error_message: Optional[str] = None
        action_str = "unknown"

        try:
            action = await _choose_action_with_retry(agent, observation, step)
            action_type_val = getattr(action.action_type, 'value', str(action.action_type))
            action_str = f"{action_type_val} on {action.target}"

            step_result = await env.step(action)
            if len(step_result) == 5:
                observation, reward, terminated, truncated, info = step_result
                done = terminated or truncated
            else:
                observation, reward, done, info = step_result

            error_message = info.get("error") if isinstance(info, dict) else None

        except Exception as exc:  # noqa: BLE001
            print(
                f"[ERROR] step={step} exception={exc!s}",
                file=sys.stderr,
                flush=True,
            )
            # IMPORTANT: use 0.05 not 0.0 — evaluator rejects exactly 0.0
            reward = 0.05
            done = True
            error_message = str(exc)

        # ── CLAMP at every possible reward origin ─────────────────────────
        # This is the single authoritative clamp point.
        # Handles: None, str, int, float, out-of-range values.
        float_reward = _clamp_reward(reward)

        rewards.append(f"{float_reward:.4f}")

        # success = episode ended cleanly with no error
        success = done and (_normalize_error(error_message) == "null")

        print(
            f"[STEP] step={step} action={action_str} reward={float_reward:.4f} "
            f"done={'true' if done else 'false'} "
            f"error={_normalize_error(error_message)}",
            flush=True,
        )

        if done:
            break

    # ── Final episode-level score guard ───────────────────────────────────
    # If evaluator aggregates rewards[], ensure no element is 0.0 or 1.0.
    safe_rewards = [_clamp_reward(r) for r in rewards]
    rewards_str = ','.join(f"{r:.4f}" for r in safe_rewards)

    print(
        f"[END] success={'true' if success else 'false'} "
        f"steps={len(rewards)} rewards={rewards_str}",
        flush=True,
    )


async def main() -> int:
    args = _parse_args()

    try:
        agent = _build_agent(args.model)
        for difficulty in EPISODE_DIFFICULTIES:
            await _run_episode(difficulty, agent)
    except HuggingFaceAgentError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr, flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
