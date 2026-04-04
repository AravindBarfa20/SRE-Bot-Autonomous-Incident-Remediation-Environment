import asyncio
from models import Action, Observation, ActionType
from graders import calculate_reward
from stream import log_to_stream

class IncidentEnv:
    def __init__(self):
        self.task = "hard"
        self.steps = 0
        self.resolved = False
        self.recent_logs = []
        self.last_action_feedback = "Environment initialized."

    async def _emit_log(self, **kwargs):
        await log_to_stream(**kwargs)
        message = kwargs.get("message", "")
        target = kwargs.get("target", "system")
        status = kwargs.get("status", "INFO")
        self.recent_logs.append(f"[{status}] {target}: {message}")
        self.recent_logs = self.recent_logs[-12:]

    def _build_logs_context(self) -> str:
        if not self.recent_logs:
            return "No logs captured yet."
        return "\n".join(self.recent_logs)

    async def reset(self):
        self.steps = 0
        self.resolved = False
        self.recent_logs = []
        self.last_action_feedback = "Environment reset."
        await self._emit_log(
            message=f"Environment Reset. Task level: {self.task.upper()}",
            target="system",
            status="INFO",
            msg_type="system"
        )
        return await self._get_obs()

    async def step(self, action: Action):
        self.steps += 1
        action_id = f"step-{self.steps}:{action.action_type.value}:{action.target}"
        self.last_action_feedback = (
            f"Agent executed {action.action_type.value} on {action.target}."
        )

        # Log action execution
        await self._emit_log(
            message=f"{action.action_type.value} on {action.target}",
            target=action.target,
            status="INFO",
            msg_type="action",
            action_name=action.action_type.value,
            action_id=action_id,
            action_status="pending",
        )

        await asyncio.sleep(1)  # Simulate network latency

        # Hard task: Config drift on db-proxy needs rollback
        is_correct = action.action_type == ActionType.ROLLBACK_CONFIG and action.target == "db-proxy"

        if is_correct:
            self.resolved = True
            self.last_action_feedback = (
                f"Rollback succeeded on {action.target}. System stability restored."
            )
            await self._emit_log(
                message=f"Config rolled back on {action.target}. Stability restored.",
                target=action.target,
                status="INFO",
                msg_type="action",
                action_name=action.action_type.value,
                action_id=action_id,
                action_status="success",
                health="healthy",
            )
        elif action.action_type == ActionType.RESOLVE and self.resolved:
            self.last_action_feedback = "Incident resolved and officially closed."
            await self._emit_log(
                message="Incident officially closed by agent.",
                target="system",
                status="INFO",
                msg_type="action",
                action_name=action.action_type.value,
                action_id=action_id,
                action_status="success",
            )
            return await self._get_obs(), calculate_reward(action, True, self.steps), True
        else:
            self.last_action_feedback = (
                f"{action.action_type.value} on {action.target} did not improve the incident."
            )
            await self._emit_log(
                message="Action had no positive effect on system health.",
                target=action.target,
                status="WARN",
                msg_type="action",
                action_name=action.action_type.value,
                action_id=action_id,
                action_status="failed",
                health="degraded",
            )

        reward = calculate_reward(action, is_correct, self.steps)
        return await self._get_obs(), reward, False

    async def _get_obs(self):
        if not self.resolved:
            # ADVERSARIAL NOISE: Hide the real error
            await self._emit_log(
                message="connection pool healthy",
                target="db-proxy",
                status="INFO",
                msg_type="system",
                health="healthy",
            )
            await self._emit_log(
                message="config hash mismatch detected - schema drift possible",
                target="db-proxy",
                status="WARN",
                msg_type="system",
                health="degraded",
            )
            await self._emit_log(
                message="telemetry flushed",
                target="db-proxy",
                status="INFO",
                msg_type="system",
                health="degraded",
            )
        else:
            await self._emit_log(
                message="System stable. Config synchronized.",
                target="db-proxy",
                status="INFO",
                msg_type="system",
                health="healthy",
            )

        return Observation(
            system_health=100.0 if self.resolved else 45.0,
            active_alerts=[] if self.resolved else ["CRITICAL: Database Latency Spike"],
            logs=self._build_logs_context(),
            metrics={"cpu": 12.0, "latency": 20.0} if self.resolved else {"cpu": 85.0, "latency": 1450.0},
            last_action_feedback=self.last_action_feedback
        )
