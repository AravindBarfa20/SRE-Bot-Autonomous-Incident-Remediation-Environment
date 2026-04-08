"""
OpenEnv-compliant inference runner for SRE-Bot.
100% compliant: no stdout leakage, deterministic LLM, env-var config.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

import httpx


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
    agent = HuggingFaceSREAgent(
        model_id=model_id,
        temperature=DEFAULT_TEMPERATURE,
        api_base_url=API_BASE_URL,
    )
    if not agent.is_configured():
        raise HuggingFaceAgentError(
            "Missing Hugging Face API token. Set HF_TOKEN environment variable."
        )
    print(
        f"[SYSTEM] Using model={model_id} base_url={agent.api_url}",
        file=sys.stderr,
        flush=True,
    )
    return agent


def _normalize_error(value: Optional[str]) -> str:
    return value if value else "null"


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
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, HuggingFaceAgentError):
        text = str(exc)
        return any(s in text for s in ("status 429", "status 502",
                                        "status 503", "status 504"))
    return False


async def _choose_action_with_retry(
    agent: HuggingFaceSREAgent, observation, step: int
) -> Action:
    if not agent.token:
        raise HuggingFaceAgentError(
            "Missing Hugging Face API token. Set HF_TOKEN."
        )

    prompt = agent._build_prompt(observation, step)
    payload = {
        "model": agent.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 220,
        "temperature": DEFAULT_TEMPERATURE,
        "seed": DEFAULT_SEED,
    }

    last_error: Optional[Exception] = None
    max_attempts = len(RETRY_DELAYS_SECONDS) + 1

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    agent.api_url,
                    headers={
                        "Authorization": f"Bearer {agent.token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            if response.status_code >= 400:
                raise HuggingFaceAgentError(
                    f"Hugging Face inference failed with "
                    f"status {response.status_code}: {response.text}"
                )

            model_text = agent._extract_generated_text(response.json())
            return _parse_action_from_text(model_text)

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= max_attempts or not _is_retryable_error(exc):
                break

            delay = RETRY_DELAYS_SECONDS[attempt - 1]
            # ── ALL retry logs → stderr only ──────────────────────────────
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

    # ── ONLY [START] goes to stdout ────────────────────────────────────────
    print(
        f"[START] task={observation.task_name} "
        f"env={observation.benchmark} model={agent.model_id}",
        flush=True,
    )

    for step in range(1, MAX_STEPS + 1):
        error_message: Optional[str] = None
        try:
            action = await _choose_action_with_retry(agent, observation, step)
            action_str = action.to_action_string()
            observation, reward, terminated, truncated, info = await env.step(
                action
            )
            done = terminated or truncated
            error_message = info.get("error")
        except Exception as exc:  # noqa: BLE001
            print(
                f"[ERROR] step={step} exception={exc!s}",
                file=sys.stderr,
                flush=True,
            )
            action_str = "invalid"
            observation, reward, terminated, truncated, info = (
                await env._handle_invalid_action(str(exc))
            )
            done = terminated or truncated
            error_message = info.get("error")

        rewards.append(f"{reward:.2f}")
        success = done and _normalize_error(error_message) == "null"

        # ── ONLY [STEP] goes to stdout ────────────────────────────────────
        print(
            f"[STEP] step={step} action={action_str} reward={reward:.2f} "
            f"done={'true' if done else 'false'} "
            f"error={_normalize_error(error_message)}",
            flush=True,
        )

        if done:
            break

    # ── ONLY [END] goes to stdout ───────────────────────────────────────────
    print(
        f"[END] success={'true' if success else 'false'} "
        f"steps={len(rewards)} rewards={','.join(rewards)}",
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
