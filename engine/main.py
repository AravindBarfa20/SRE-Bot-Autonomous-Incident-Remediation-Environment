from __future__ import annotations

import asyncio
import os

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

try:
    from .agent import HuggingFaceAgentError, HuggingFaceSREAgent
    from .env import IncidentEnv
    from .models import Action
    from .stream import event_generator
except ImportError:
    from agent import HuggingFaceAgentError, HuggingFaceSREAgent
    from env import IncidentEnv
    from models import Action
    from stream import event_generator

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

app = FastAPI(title="SRE-Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IncidentEnv()
agent = HuggingFaceSREAgent()


async def _run_agent_loop(max_steps: int = 8) -> None:
    observation = await env.reset()

    if not agent.is_configured():
        raise HuggingFaceAgentError(
            "Hugging Face API token not configured. Set HF_TOKEN."
        )

    await env._emit_log(
        message="Agent loop started.",
        target="llm-agent",
        status="INFO",
        msg_type="system",
    )

    done = False
    for step in range(1, max_steps + 1):
        try:
            action = await agent.choose_action(observation, step)
        except HuggingFaceAgentError as exc:
            observation, _, terminated, truncated, _ = await env._handle_invalid_action(str(exc))
            done = terminated or truncated
            if done:
                break
            await asyncio.sleep(1)
            continue

        observation, _, terminated, truncated, _ = await env.step(action)
        done = terminated or truncated
        if done:
            break

        await asyncio.sleep(1)

    if not done:
        await env._emit_log(
            message="Max steps reached without resolution.",
            target="llm-agent",
            status="WARN",
            msg_type="system",
        )


@app.get("/api/stream-logs")
async def stream_logs(request: Request):
    last_event_id = request.headers.get("last-event-id")
    return StreamingResponse(
        event_generator(last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/trigger-demo")
@app.post("/api/run-agent")
async def trigger_demo(background_tasks: BackgroundTasks):
    async def _run() -> None:
        try:
            await _run_agent_loop()
        except Exception as exc:
            await env._emit_log(
                message=f"Agent loop error: {exc}",
                target="llm-agent",
                status="ERROR",
                msg_type="system",
            )

    background_tasks.add_task(_run)
    return {"status": "started", "model": agent.model_id}


@app.post("/reset")
@app.post("/api/reset")
async def openenv_reset():
    observation = await env.reset()
    return observation.model_dump(mode="json")


@app.post("/step")
@app.post("/api/step")
async def openenv_step(action: Action):
    observation, reward, terminated, truncated, info = await env.step(action)
    return {
        "observation": observation.model_dump(mode="json"),
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


@app.get("/state")
@app.get("/api/state")
async def get_state():
    return env.get_state_snapshot().model_dump(mode="json")
