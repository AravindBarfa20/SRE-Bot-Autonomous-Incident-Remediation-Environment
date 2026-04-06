from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    CHECK_LOGS = "check_logs"
    CHECK_METRICS = "check_metrics"
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    ROLLBACK_CONFIG = "rollback_config"
    RESOLVE = "resolve"


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target: str = Field(min_length=1)  # e.g., "auth-service", "api-gateway", "db-proxy"
    rationale: Optional[str] = None

    def to_action_string(self) -> str:
        return f"{self.action_type.value}:{self.target}"


class NodeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: float
    ram: float
    latency: float


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark: str
    task_name: str
    step_count: int
    system_health: int  # 0 to 100
    active_alerts: List[str]
    logs: str
    metrics: Dict[str, NodeMetrics]
    available_actions: List[str]
    last_action_feedback: str


class RewardBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reward: float
    incident_cost_delta: float
    root_cause_identified: bool = False
    unnecessary_action: bool = False
    resolution_verified: bool = False
    error: Optional[str] = None


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark: str
    current_task: str
    steps_taken: int
    fault_resolved: bool
    history: List[Action] = Field(default_factory=list)
    root_cause_identified: bool = False
    unnecessary_actions_count: int = 0
    system_health_history: List[int] = Field(default_factory=list)
    awarded_milestones: List[str] = Field(default_factory=list)
    remediation_applied: bool = False
    verification_complete: bool = False
    incident_cost: float = 0.0
    last_error: Optional[str] = None
