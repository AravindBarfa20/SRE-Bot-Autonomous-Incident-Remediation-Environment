export type MessageType = "action" | "system";

export type HealthStatus = "healthy" | "degraded" | "critical";

export type ActionStatus = "success" | "pending" | "failed";

export interface LogEntry {
  id: string;
  eventId: string;
  message: string;
  target: string;
  status: "INFO" | "WARN" | "ERROR";
  type: MessageType;
  timestamp: string;
}

export interface ActionEntry {
  id: string;
  actionKey: string;
  action: string;
  target: string;
  status: ActionStatus;
  timestamp: string;
}

export interface SystemHealth {
  auth: HealthStatus;
  gateway: HealthStatus;
  db: HealthStatus;
}

export interface ParsedLog {
  id: string;
  sequence: number;
  timestamp: string;
  message: string;
  target: string;
  status: "INFO" | "WARN" | "ERROR";
  type: MessageType;
  actionName?: string;
  actionId?: string;
  actionStatus?: ActionStatus;
  health?: HealthStatus;
}
