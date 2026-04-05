import json
import os
from typing import Any, Optional, Union

import httpx

from models import Action, ActionType, Observation
from stream import log_to_stream


HF_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"
HF_CHAT_COMPLETIONS_URL = "{}/chat/completions".format(HF_ROUTER_BASE_URL)
VALID_TARGETS = ["auth-service", "api-gateway", "db-proxy", "system"]


class HuggingFaceAgentError(RuntimeError):
    pass


def _json_default(value: Any):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return value


class HuggingFaceSREAgent:
    def __init__(self, token: Optional[str] = None, model_id: str = HF_MODEL_ID):
        self.token = token or os.getenv("HF_TOKEN")
        self.model_id = model_id
        self.base_url = HF_ROUTER_BASE_URL
        self.api_url = HF_CHAT_COMPLETIONS_URL

    def is_configured(self) -> bool:
        return bool(self.token)

    async def choose_action(self, observation: Observation, step: int) -> Action:
        if not self.token:
            raise HuggingFaceAgentError(
                "Missing Hugging Face API token. Set HF_TOKEN."
            )

        prompt = self._build_prompt(observation, step)
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "max_tokens": 220,
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            if response.status_code >= 400:
                raise HuggingFaceAgentError(
                    f"Hugging Face inference failed with status {response.status_code}: {response.text}"
                )

            model_text = self._extract_generated_text(response.json())
            decision = self._parse_decision(model_text)
        except (httpx.HTTPError, HuggingFaceAgentError) as exc:
            await log_to_stream(
                message=f"[SYSTEM] Model invocation failed for {self.model_id}: {exc}",
                target="llm-agent",
                status="ERROR",
                msg_type="system",
            )
            raise

        reasoning = decision.get("reasoning", "").strip()
        if reasoning:
            await log_to_stream(
                message=f"[THINKING] {reasoning}",
                target="llm-agent",
                status="INFO",
                msg_type="system",
            )

        action_type_value = decision["action_type"]
        target = decision["target"]

        return Action(
            action_type=ActionType(action_type_value),
            target=target,
            rationale=reasoning or "No rationale provided by model.",
        )

    def _build_prompt(self, observation: Observation, step: int) -> str:
        valid_action_types = ", ".join(action.value for action in ActionType)
        valid_targets = ", ".join(VALID_TARGETS)
        json_default = _json_default
        return f"""
You are SRE-Bot, an incident remediation agent operating in a production-grade RL environment.
You must inspect the current observation and choose exactly one next action.

Rules:
- Respond with JSON only.
- JSON schema:
  {{
    "reasoning": "short explanation of what signal matters most",
    "action_type": "one of: {valid_action_types}",
    "target": "one of: {valid_targets}"
  }}
- Prefer non-destructive inspection before remediation unless evidence is strong.
- If the incident is already resolved and stable, choose action_type "resolve" with target "system".
- The known failure pattern for this task is config drift on db-proxy, but adversarial logs may include noise.

Observation step: {step}
System health score: {observation.system_health}
Active alerts: {json.dumps(observation.active_alerts, default=json_default)}
Available actions: {json.dumps(observation.available_actions, default=json_default)}
Metrics: {json.dumps(observation.metrics, default=json_default)}
Last action feedback: {observation.last_action_feedback}
Recent logs:
{observation.logs}
""".strip()

    def _extract_generated_text(self, payload: Union[Any, dict, list]) -> str:
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_value = item.get("text")
                                    if isinstance(text_value, str):
                                        text_parts.append(text_value)
                            if text_parts:
                                return "\n".join(text_parts)
            error = payload.get("error")
            if error:
                raise HuggingFaceAgentError(str(error))
        raise HuggingFaceAgentError(f"Unexpected Hugging Face response payload: {payload!r}")

    def _parse_decision(self, model_text: str) -> dict[str, str]:
        start = model_text.find("{")
        end = model_text.rfind("}")
        candidate = model_text[start : end + 1] if start != -1 and end != -1 else model_text

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise HuggingFaceAgentError(f"Model did not return valid JSON: {model_text}") from exc

        action_type = parsed.get("action_type")
        target = parsed.get("target")
        if action_type not in {action.value for action in ActionType}:
            raise HuggingFaceAgentError(f"Invalid action_type from model: {action_type!r}")
        if target not in VALID_TARGETS:
            raise HuggingFaceAgentError(f"Invalid target from model: {target!r}")

        return {
            "reasoning": str(parsed.get("reasoning", "")),
            "action_type": str(action_type),
            "target": str(target),
        }
