from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

class ActionType(Enum):
    CHECK_LOGS = "check_logs"
    CHECK_METRICS = "check_metrics"
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    ROLLBACK_CONFIG = "rollback_config"
    RESOLVE = "resolve"

class Action(BaseModel):
    action_type: ActionType
    target: str  # e.g., "auth-service", "api-gateway", "db-proxy"
    rationale: Optional[str] = None


class NodeMetrics(BaseModel):
    cpu: float
    ram: float
    latency: float


class Observation(BaseModel):
    system_health: float  # 0.0 to 100.0
    active_alerts: List[str]
    logs: str
    metrics: Dict[str, NodeMetrics]
    available_actions: List[str]
    last_action_feedback: str

class State(BaseModel):
    current_task: str
    steps_taken: int
    fault_resolved: bool
    history: List[Action]
