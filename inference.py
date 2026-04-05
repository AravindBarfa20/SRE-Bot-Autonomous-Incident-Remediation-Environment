import argparse
import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

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
    parser = argparse.ArgumentParser(description="Standardized OpenEnv evaluation runner.")
    parser.add_argument(
        "--model",
        default="qwen-7b",
        choices=sorted(MODEL_ALIASES),
        help="Agent model alias to use for all episodes.",
    )
    return parser.parse_args()


def build_agent(model_alias: str) -> HuggingFaceSREAgent:
    model_id = MODEL_ALIASES[model_alias]
    agent = HuggingFaceSREAgent(model_id=model_id)
    if not agent.is_configured():
        raise HuggingFaceAgentError("Missing Hugging Face API token. Set HF_TOKEN.")
    logging.getLogger("openenv.eval").info("Using model %s", model_id)
    return agent


def format_action(action) -> str:
    return json.dumps(
        {
            "action_type": action.action_type.value,
            "target": action.target,
        },
        separators=(",", ":"),
    )


async def run_episode(episode_number: int, difficulty: str, agent: HuggingFaceSREAgent) -> None:
    env = IncidentEnv(difficulty=difficulty)
    observation = await env.reset()
    total_reward = 0.0

    print(f"[START] Episode {episode_number}", flush=True)

    for step in range(1, MAX_STEPS + 1):
        action = await agent.choose_action(observation, step)
        print(
            f"[STEP] Reasoning: {action.rationale} | Action: {format_action(action)}",
            flush=True,
        )

        observation, reward, done = await env.step(action)
        total_reward += reward

        if done:
            break

    print(f"[END] Reward: {total_reward:.2f}", flush=True)


async def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        agent = build_agent(args.model)
        for episode_number, difficulty in enumerate(EPISODE_DIFFICULTIES, start=1):
            await run_episode(episode_number, difficulty, agent)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("openenv.eval").exception("Evaluation run failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
