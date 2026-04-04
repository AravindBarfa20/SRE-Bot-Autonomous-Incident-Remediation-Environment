import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from agent import HuggingFaceSREAgent, HuggingFaceAgentError
from stream import event_generator
from env import IncidentEnv

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency for local development
    def load_dotenv() -> bool:
        return False


load_dotenv()

app = FastAPI(title="SRE-Bot API")

# Allow Next.js frontend to connect during local development.
# TODO: Replace "*" with an explicit allowlist of production dashboard origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IncidentEnv()
agent = HuggingFaceSREAgent()


async def run_agent_loop(max_steps: int = 8):
    observation = await env.reset()

    if not agent.is_configured():
        raise HuggingFaceAgentError(
            "Hugging Face API token is not configured. Set HF_TOKEN."
        )

    await env._emit_log(
        message="LLM agent loop started. Streaming reasoning and actions.",
        target="llm-agent",
        status="INFO",
        msg_type="system",
    )

    done = False
    for step in range(1, max_steps + 1):
        await env._emit_log(
            message=(
                f"[THINKING] Step {step}: health={observation.system_health}, "
                f"alerts={observation.active_alerts}, metrics={observation.metrics}"
            ),
            target="llm-agent",
            status="INFO",
            msg_type="system",
        )

        action = await agent.choose_action(observation, step)
        await env._emit_log(
            message=(
                f"[THINKING] Chosen action: {action.action_type.value} on {action.target}. "
                f"Rationale: {action.rationale}"
            ),
            target="llm-agent",
            status="INFO",
            msg_type="system",
        )

        observation, reward, done = await env.step(action)
        await env._emit_log(
            message=(
                f"[THINKING] Step {step} complete. Reward={reward:.2f}. "
                f"Resolved={done}. Feedback={observation.last_action_feedback}"
            ),
            target="llm-agent",
            status="INFO",
            msg_type="system",
        )

        if done:
            break

        await asyncio.sleep(1)

    if not done:
        await env._emit_log(
            message="Max agent steps reached before resolution.",
            target="llm-agent",
            status="WARN",
            msg_type="system",
        )

@app.get("/api/stream-logs")
async def stream_logs(request: Request):
    """SSE Endpoint for Next.js to consume real-time logs."""
    last_event_id = request.headers.get("last-event-id")
    return StreamingResponse(
        event_generator(last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/trigger-demo")
async def trigger_demo(background_tasks: BackgroundTasks):
    """Start a real LLM-driven remediation loop and stream its reasoning to the UI."""
    async def run_with_logging():
        try:
            await run_agent_loop()
        except HuggingFaceAgentError as exc:
            await env._emit_log(
                message=f"LLM agent configuration error: {exc}",
                target="llm-agent",
                status="ERROR",
                msg_type="system",
            )
        except Exception as exc:  # noqa: BLE001
            await env._emit_log(
                message=f"LLM agent loop failed unexpectedly: {exc}",
                target="llm-agent",
                status="ERROR",
                msg_type="system",
            )

    background_tasks.add_task(run_with_logging)
    return {
        "status": "LLM remediation loop started",
        "model": agent.model_id,
    }


@app.post("/api/run-agent")
async def run_agent(background_tasks: BackgroundTasks):
    return await trigger_demo(background_tasks)
