import argparse
import asyncio
import logging
import sys
import warnings
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "engine"
for candidate in (str(ROOT), str(ENGINE_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from agent import HF_MODEL_ID, HuggingFaceAgentError, HuggingFaceSREAgent
from env import IncidentEnv


MODEL_ALIASES = {
    "qwen-7b": HF_MODEL_ID,
    "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.3",
}
EPISODE_DIFFICULTIES = ("easy", "medium", "hard")
MAX_STEPS = 8


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )
    warnings.simplefilter("default")
    logging.captureWarnings(True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenEnv-compliant evaluation runner.")
    parser.add_argument(
        "--model",
        default="qwen-7b",
        choices=sorted(MODEL_ALIASES),
        help="Agent model alias to use for all benchmark tasks.",
    )
    return parser.parse_args()


def build_agent(model_alias: str) -> HuggingFaceSREAgent:
    model_id = MODEL_ALIASES[model_alias]
    agent = HuggingFaceSREAgent(model_id=model_id, temperature=0.0)
    if not agent.is_configured():
        raise HuggingFaceAgentError("Missing Hugging Face API token. Set HF_TOKEN.")
    logging.getLogger("openenv.eval").info("Using model %s", model_id)
    return agent


def normalize_error(value: Optional[str]) -> str:
    return value if value else "null"


async def run_episode(difficulty: str, agent: HuggingFaceSREAgent) -> None:
    env = IncidentEnv(difficulty=difficulty)
    observation = await env.reset()
    rewards: List[str] = []
    success = False

    print(
        f"[START] task={observation.task_name} env={observation.benchmark} model={agent.model_id}",
        flush=True,
    )

    for step in range(1, MAX_STEPS + 1):
        error_message = None
        try:
            action = await agent.choose_action(observation, step)
            action_str = action.to_action_string()
            observation, reward, terminated, truncated, info = await env.step(action)
            done = terminated or truncated
            error_message = info.get("error")
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("openenv.eval").exception(
                "Episode generated an invalid action at step %s for task %s: %s",
                step,
                env.task,
                exc,
            )
            action_str = "invalid"
            observation, reward, terminated, truncated, info = await env._handle_invalid_action(
                str(exc)
            )
            done = terminated or truncated
            error_message = info.get("error")

        rewards.append(f"{reward:.2f}")
        success = done and normalize_error(error_message) == "null"
        print(
            f"[STEP] step={step} action={action_str} reward={reward:.2f} "
            f"done={'true' if done else 'false'} error={normalize_error(error_message)}",
            flush=True,
        )

        if done:
            break

    print(
        f"[END] success={'true' if success else 'false'} "
        f"steps={len(rewards)} rewards={','.join(rewards)}",
        flush=True,
    )


async def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        agent = build_agent(args.model)
        for difficulty in EPISODE_DIFFICULTIES:
            await run_episode(difficulty, agent)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("openenv.eval").exception("Evaluation run failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
