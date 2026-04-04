"use client";

import { useRef, useEffect } from "react";
import { LogEntry } from "@/lib/types";

interface AdversarialTerminalProps {
  logs: LogEntry[];
  isConnected: boolean;
  connectionError: string | null;
}

const levelStyles: Record<string, { color: string; bg: string }> = {
  INFO: { color: "text-emerald-400", bg: "bg-emerald-500/10" },
  WARN: { color: "text-amber-400", bg: "bg-amber-500/10" },
  ERROR: { color: "text-red-400", bg: "bg-red-500/10" },
};

export function AdversarialTerminal({
  logs,
  isConnected,
  connectionError,
}: AdversarialTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-full w-full flex flex-col rounded-lg border border-zinc-800 bg-black overflow-hidden">
      {/* Terminal header */}
      <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-2 bg-zinc-950">
        <div className="flex gap-1.5">
          <div className="h-2 w-2 rounded-full bg-red-500" />
          <div className="h-2 w-2 rounded-full bg-amber-500" />
          <div className="h-2 w-2 rounded-full bg-emerald-500" />
        </div>
        <span className="ml-2 text-xs font-mono text-zinc-500">
          adversarial-terminal — sre-bot
        </span>
        <div className="ml-auto flex items-center gap-2">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              isConnected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
            }`}
          />
          <span className="text-[10px] font-mono text-zinc-600">
            {isConnected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
      </div>

      {/* Terminal body */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto overflow-x-hidden p-3 font-mono text-xs leading-relaxed"
      >
        {connectionError && (
          <div className="text-amber-400 mb-2">[SYSTEM] {connectionError}</div>
        )}

        {logs.length === 0 && isConnected && (
          <div className="text-zinc-600 italic">Waiting for logs...</div>
        )}

        {logs.map((log) => (
          <div
            key={log.id}
            className="flex gap-2 py-0.5 hover:bg-zinc-900/50 group"
          >
            <span className="text-zinc-600 shrink-0 w-[70px]">
              {log.timestamp}
            </span>
            <span
              className={`shrink-0 w-12 px-1 rounded text-[10px] font-bold ${
                levelStyles[log.status]?.color || "text-zinc-400"
              } ${levelStyles[log.status]?.bg || ""}`}
            >
              {log.status}
            </span>
            <span className="text-cyan-400 shrink-0 w-24 truncate">
              {log.target}
            </span>
            <span className="text-zinc-300 flex-1">{log.message}</span>
          </div>
        ))}
        <div className="mt-2 flex items-center gap-1 text-emerald-500">
          <span className="text-zinc-600">$</span>
          <span className="animate-pulse">▊</span>
        </div>
      </div>
    </div>
  );
}