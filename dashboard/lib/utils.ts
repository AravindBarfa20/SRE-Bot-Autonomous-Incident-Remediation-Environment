import {
  ParsedLog,
  ActionEntry,
  ActionStatus,
  SystemHealth,
  HealthStatus,
} from "./types";

/**
 * Generate a unique ID for log entries and actions.
 */
export function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Parse incoming SSE data into a structured log object.
 */
export function parseLog(data: string): ParsedLog | null {
  const payload = data.trim();
  if (!payload) {
    return null;
  }

  try {
    const json = JSON.parse(payload);
    const status = ["INFO", "WARN", "ERROR"].includes(json.status?.toUpperCase())
      ? json.status.toUpperCase()
      : "INFO";
    const actionStatus = ["pending", "success", "failed"].includes(json.action_status)
      ? json.action_status
      : undefined;
    const health = ["healthy", "degraded", "critical"].includes(json.health)
      ? json.health
      : undefined;

    return {
      id: json.id || generateId(),
      sequence: typeof json.sequence === "number" ? json.sequence : 0,
      timestamp: json.timestamp || new Date().toISOString(),
      message: json.message || "",
      target: json.target || "system",
      status: status as "INFO" | "WARN" | "ERROR",
      type: json.type === "action" ? "action" : "system",
      actionName: json.action_name || undefined,
      actionId: json.action_id || undefined,
      actionStatus: actionStatus as ActionStatus | undefined,
      health: health as HealthStatus | undefined,
      metadata: json.metadata || undefined,
    };
  } catch {
    let status: "INFO" | "WARN" | "ERROR" = "INFO";
    let target = "system";

    if (payload.startsWith("[ERROR]")) {
      status = "ERROR";
    } else if (payload.startsWith("[WARN]")) {
      status = "WARN";
    }

    if (payload.startsWith("[THINKING]")) {
      target = "llm-agent";
    } else if (payload.startsWith("[SYSTEM]")) {
      target = "system";
    }

    return {
      id: generateId(),
      sequence: 0,
      timestamp: new Date().toISOString(),
      message: payload,
      target,
      status,
      type: "system",
    };
  }
}

/**
 * Map backend target names to frontend node keys.
 */
const TARGET_TO_NODE: Record<string, keyof SystemHealth> = {
  "auth-service": "auth",
  "api-gateway": "gateway",
  "db-proxy": "db",
};

/**
 * Determine health status from log message.
 */
export function getHealthFromLog(
  message: string,
  target: string,
  status: string,
  explicitHealth?: HealthStatus
): { node: keyof SystemHealth; health: HealthStatus } | null {
  const node = TARGET_TO_NODE[target] || (target as keyof SystemHealth);

  // Check if node exists in our system
  if (!["auth", "gateway", "db"].includes(node)) {
    return null;
  }

  if (explicitHealth) {
    return { node, health: explicitHealth };
  }

  // SUCCESS + db-proxy → healthy
  if (
    (message.toLowerCase().includes("success") ||
      message.toLowerCase().includes("stability restored") ||
      message.toLowerCase().includes("stable")) &&
    target === "db-proxy"
  ) {
    return { node: "db", health: "healthy" };
  }

  // INFO status indicates healthy
  if (status === "INFO") {
    return { node, health: "healthy" };
  }

  // WARN indicates degraded
  if (status === "WARN") {
    return { node, health: "degraded" };
  }

  // ERROR indicates critical
  if (status === "ERROR") {
    return { node, health: "critical" };
  }

  return null;
}

/**
 * Map log status to action status.
 */
const STATUS_MAP: Record<string, ActionStatus> = {
  INFO: "success",
  WARN: "pending",
  ERROR: "failed",
};

/**
 * Check if log should create an action entry.
 * Actions are created for logs starting with [EXECUTING] or type: action.
 */
export function shouldCreateAction(message: string, type: string): boolean {
  if (type === "action") return true;
  if (message.startsWith("[EXECUTING]")) return true;
  return false;
}

export function parseExecutingLog(message: string, fallbackTarget: string): {
  action: string;
  target: string;
} | null {
  if (!message.startsWith("[EXECUTING]")) {
    return null;
  }

  const payload = message.replace("[EXECUTING]", "").trim();
  const onMatch = payload.match(/^([^\s]+)\s+on\s+([^\s]+)$/i);
  if (onMatch) {
    return {
      action: onMatch[1],
      target: onMatch[2],
    };
  }

  const [action] = payload.split(/\s+/, 1);
  if (!action) {
    return null;
  }

  return {
    action,
    target: fallbackTarget,
  };
}

/**
 * Create an action entry from a log.
 */
export function createActionFromLog(
  actionId: string | undefined,
  actionName: string | undefined,
  message: string,
  target: string,
  status: "INFO" | "WARN" | "ERROR",
  actionStatus?: ActionStatus
): ActionEntry {
  // Extract action name from message
  let resolvedActionName = actionName || message;
  if (message.startsWith("[EXECUTING]")) {
    resolvedActionName = message.replace("[EXECUTING]", "").trim().split(" ")[0];
  } else if (message.startsWith("[SUCCESS]")) {
    resolvedActionName = message.replace("[SUCCESS]", "").trim().split(" ")[0];
  } else if (message.startsWith("[FAILED]")) {
    resolvedActionName = message.replace("[FAILED]", "").trim().split(" ")[0];
  }

  const normalizedActionName = resolvedActionName || message.slice(0, 20);
  const actionKey = actionId || `${target}:${normalizedActionName}`;

  return {
    id: generateId(),
    actionKey,
    action: normalizedActionName,
    target,
    status: actionStatus || STATUS_MAP[status] || "pending",
    timestamp: new Date().toISOString().slice(11, 22),
  };
}

export function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString().slice(11, 22);
  }
  return date.toISOString().slice(11, 22);
}

export function upsertActionEntry(
  previous: ActionEntry[],
  nextAction: ActionEntry
): ActionEntry[] {
  const index = previous.findIndex((entry) => entry.actionKey === nextAction.actionKey);
  if (index === -1) {
    return [...previous, nextAction];
  }

  const updated = [...previous];
  updated[index] = {
    ...updated[index],
    ...nextAction,
    id: updated[index].id,
    actionKey: updated[index].actionKey,
  };
  return updated;
}
