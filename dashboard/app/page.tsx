"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { TopologyMap } from "@/components/topology-map";
import { AdversarialTerminal } from "@/components/adversarial-terminal";
import { ActionLedger } from "@/components/action-ledger";
import { LogEntry, ActionEntry, SystemHealth } from "@/lib/types";
import {
  parseLog,
  generateId,
  formatEventTime,
  getHealthFromLog,
  shouldCreateAction,
  createActionFromLog,
  parseExecutingLog,
  upsertActionEntry,
} from "@/lib/utils";

const INITIAL_HEALTH: SystemHealth = {
  auth: "healthy",
  gateway: "healthy",
  db: "degraded",
};
const STREAM_LOGS_URL = "/api/stream-logs";
const MAX_LOG_ENTRIES = 250;
const MAX_RECONNECT_DELAY_MS = 30000;
const INITIAL_RECONNECT_DELAY_MS = 1000;

export default function Dashboard() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [actions, setActions] = useState<ActionEntry[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemHealth>(INITIAL_HEALTH);
  const [incidentCost, setIncidentCost] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const seenEventIdsRef = useRef<Set<string>>(new Set());
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const isUnmountedRef = useRef(false);

  const processLog = useCallback((parsed: ReturnType<typeof parseLog>) => {
    if (!parsed) return;
    if (seenEventIdsRef.current.has(parsed.id)) return;

    seenEventIdsRef.current.add(parsed.id);
    const clientLogId = generateId();
    const formattedTimestamp = formatEventTime(parsed.timestamp);

    const logEntry: LogEntry = {
      id: clientLogId,
      eventId: parsed.id,
      message: parsed.message,
      target: parsed.target,
      status: parsed.status,
      type: parsed.type,
      timestamp: formattedTimestamp,
    };

    setLogs((prev) => {
      const nextLogs = [...prev, logEntry];
      return nextLogs.slice(-MAX_LOG_ENTRIES);
    });

    const nextIncidentCost = parsed.metadata?.state?.incident_cost;
    if (typeof nextIncidentCost === "number") {
      setIncidentCost(nextIncidentCost);
    }

    const healthUpdate = getHealthFromLog(
      parsed.message,
      parsed.target,
      parsed.status,
      parsed.health
    );
    if (healthUpdate) {
      setSystemStatus((prev) => ({
        ...prev,
        [healthUpdate.node]: healthUpdate.health,
      }));
    }

    if (
      parsed.message.toUpperCase().includes("SUCCESS") &&
      parsed.target === "db-proxy"
    ) {
      setSystemStatus((prev) => ({
        ...prev,
        db: "healthy",
      }));
    }

    if (shouldCreateAction(parsed.message, parsed.type)) {
      const executingDetails = parseExecutingLog(parsed.message, parsed.target);
      const actionEntry = createActionFromLog(
        parsed.actionId,
        executingDetails?.action || parsed.actionName,
        parsed.message,
        executingDetails?.target || parsed.target,
        parsed.status,
        parsed.actionStatus || (executingDetails ? "pending" : undefined)
      );
      actionEntry.id = generateId();
      actionEntry.timestamp = formattedTimestamp;
      setActions((prev) => upsertActionEntry(prev, actionEntry));
    }
  }, []);

  useEffect(() => {
    isUnmountedRef.current = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const closeEventSource = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (isUnmountedRef.current || reconnectTimerRef.current !== null) {
        return;
      }

      const attempt = reconnectAttemptRef.current + 1;
      reconnectAttemptRef.current = attempt;
      const delay = Math.min(
        INITIAL_RECONNECT_DELAY_MS * 2 ** (attempt - 1),
        MAX_RECONNECT_DELAY_MS
      );

      setConnectionError(`Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`);
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      clearReconnectTimer();
      closeEventSource();

      const eventSource = new EventSource(STREAM_LOGS_URL);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        reconnectAttemptRef.current = 0;
        clearReconnectTimer();
        setIsConnected(true);
        setConnectionError(null);
        console.log("SSE Connected");
      };

      eventSource.onmessage = (event) => {
        const parsed = parseLog(event.data);
        if (parsed) {
          processLog(parsed);
        }
      };

      eventSource.onerror = (error) => {
        setIsConnected(false);

        if (eventSource.readyState === EventSource.CONNECTING) {
          closeEventSource();
          scheduleReconnect();
          return;
        }

        if (eventSource.readyState === EventSource.CLOSED) {
          console.error("SSE connection error", {
            url: STREAM_LOGS_URL,
            readyState: eventSource.readyState,
            error,
          });
          closeEventSource();
          scheduleReconnect();
          return;
        }

        setConnectionError("Connection lost.");
      };
    };

    connect();

    return () => {
      isUnmountedRef.current = true;
      clearReconnectTimer();
      closeEventSource();
    };
  }, [processLog]);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-black">
      {/* Fixed Header */}
      <header className="flex flex-shrink-0 items-center justify-between border-b border-zinc-800 px-6 py-3 bg-black">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
            <span className="text-xs font-bold text-black">SR</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-100">SRE-Bot</h1>
            <p className="text-xs text-zinc-500">Incident Remediation RL Environment</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-1">
            <span className="text-xs font-semibold text-red-400">
              Cost of Outage: ${incidentCost.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${
                isConnected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
              }`}
            />
            <span className="text-xs text-zinc-400">
              {isConnected ? "Environment Active" : "Disconnected"}
            </span>
          </div>
          <div className="text-xs font-mono text-zinc-600">
            {new Date().toISOString().slice(0, 10)}
          </div>
        </div>
      </header>

      {/* 3-Pane Layout - Strict Percentages */}
      <div className="flex flex-1 min-h-0">
        {/* Left Pane: Topology Map (30%) */}
        <div className="w-[30%] flex-shrink-0 border-r border-zinc-800 p-3">
          <div className="h-full w-full rounded-lg border border-emerald-500/30 bg-zinc-950 overflow-hidden">
            <TopologyMap systemHealth={systemStatus} />
          </div>
        </div>

        {/* Center Pane: Adversarial Terminal (50%) */}
        <div className="w-[50%] flex-shrink-0 p-3">
          <AdversarialTerminal
            logs={logs}
            isConnected={isConnected}
            connectionError={connectionError}
          />
        </div>

        {/* Right Pane: Action Ledger (20%) */}
        <div className="w-[20%] flex-shrink-0 border-l border-zinc-800 p-3">
          <ActionLedger actions={actions} />
        </div>
      </div>
    </div>
  );
}
