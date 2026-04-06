import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from itertools import count
from typing import Any, AsyncGenerator, Literal, Optional

MessageType = Literal["action", "system"]
ActionStatus = Literal["pending", "success", "failed"]
HealthStatus = Literal["healthy", "degraded", "critical"]
KEEP_ALIVE_INTERVAL_SECONDS = 15

_event_sequence = count(1)
_event_history: deque[tuple[str, str]] = deque(maxlen=250)
_subscribers: set[asyncio.Queue[tuple[str, str]]] = set()


def _new_event_id(sequence: int) -> str:
    return f"evt-{sequence}"


def _encode_sse(event_id: str, payload: str) -> str:
    return f"id: {event_id}\ndata: {payload}\n\n"


def _normalize_status(status: str) -> str:
    normalized = status.upper()
    return normalized if normalized in {"INFO", "WARN", "ERROR"} else "INFO"


async def log_to_stream(
    message: str,
    target: str = "system",
    status: str = "INFO",
    msg_type: MessageType = "system",
    action_name: Optional[str] = None,
    action_id: Optional[str] = None,
    action_status: Optional[ActionStatus] = None,
    health: Optional[HealthStatus] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """
    Push a structured log entry to every active SSE subscriber.

    Args:
        message: The log message content
        target: The service/component this log relates to (e.g., "api-gateway", "db-proxy")
        status: Log level - "INFO", "WARN", or "ERROR"
        msg_type: Either "action" for agent actions or "system" for system events
        action_name: Normalized action identifier when the event belongs to the remediation ledger
        action_id: Correlation ID for one action lifecycle across pending/result events
        action_status: Pending/success/failed state for action ledger updates
        health: Optional explicit health state for topology updates
    """
    sequence = next(_event_sequence)
    event_id = _new_event_id(sequence)

    payload = {
        "id": event_id,
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "message": message,
        "target": target,
        "status": _normalize_status(status),
        "type": msg_type,
        "action_name": action_name,
        "action_id": action_id,
        "action_status": action_status,
        "health": health,
        "metadata": metadata,
    }
    encoded_payload = json.dumps(payload)

    _event_history.append((event_id, encoded_payload))
    for subscriber in list(_subscribers):
        try:
            await subscriber.put((event_id, encoded_payload))
        except RuntimeError:
            _subscribers.discard(subscriber)


async def event_generator(last_event_id: Optional[str] = None) -> AsyncGenerator[str, None]:
    """Yield SSE frames for one connected client, with dedupe-safe event IDs."""
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    _subscribers.add(queue)

    try:
        if last_event_id:
            replay = False
            for event_id, payload in _event_history:
                if replay:
                    yield _encode_sse(event_id, payload)
                if event_id == last_event_id:
                    replay = True

        while True:
            try:
                event_id, payload = await asyncio.wait_for(
                    queue.get(), timeout=KEEP_ALIVE_INTERVAL_SECONDS
                )
                try:
                    yield _encode_sse(event_id, payload)
                except (asyncio.CancelledError, ConnectionError, RuntimeError):
                    break
            except asyncio.TimeoutError:
                try:
                    yield ": keep-alive\n\n"
                except (asyncio.CancelledError, ConnectionError, RuntimeError):
                    break
    finally:
        _subscribers.discard(queue)
