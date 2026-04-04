"use client";

import { ActionEntry } from "@/lib/types";

interface ActionLedgerProps {
  actions: ActionEntry[];
}

const statusConfig: Record<
  string,
  { color: string; bg: string; dot: string }
> = {
  success: {
    color: "text-emerald-400",
    bg: "bg-emerald-500",
    dot: "bg-emerald-500",
  },
  pending: {
    color: "text-amber-400",
    bg: "bg-amber-500",
    dot: "bg-amber-500",
  },
  failed: {
    color: "text-red-400",
    bg: "bg-red-500",
    dot: "bg-red-500",
  },
};

export function ActionLedger({ actions }: ActionLedgerProps) {
  const successCount = actions.filter((a) => a.status === "success").length;
  const pendingCount = actions.filter((a) => a.status === "pending").length;
  const failedCount = actions.filter((a) => a.status === "failed").length;

  return (
    <div className="h-full w-full flex flex-col rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-zinc-800 px-3 py-2 bg-zinc-950">
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          Action Ledger
        </h2>
        <p className="mt-0.5 text-[8px] text-zinc-600">AI Agent Audit Trail</p>
      </div>

      {/* Action list */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 space-y-1.5">
        {actions.length === 0 && (
          <div className="text-[10px] text-zinc-600 italic text-center py-4">
            No actions recorded yet
          </div>
        )}
        {actions.map((action) => {
          const config = statusConfig[action.status];
          return (
            <div
              key={action.id}
              className="rounded border border-zinc-800 bg-zinc-900/50 p-2 hover:bg-zinc-900 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[8px] font-mono text-zinc-500">
                  {action.timestamp}
                </span>
                <div className="flex items-center gap-1.5">
                  <div
                    className={`h-1.5 w-1.5 rounded-full ${config.dot} ${
                      action.status === "pending" ? "animate-pulse" : ""
                    }`}
                  />
                </div>
              </div>
              <div className="font-mono text-[10px]">
                <span className="text-cyan-400">{'"action"'}</span>
                <span className="text-zinc-600">: </span>
                <span className="text-emerald-400">{`"${action.action}"`}</span>
              </div>
              <div className="font-mono text-[10px]">
                <span className="text-cyan-400">{'"target"'}</span>
                <span className="text-zinc-600">: </span>
                <span className="text-amber-400">{`"${action.target}"`}</span>
              </div>
              <div className="mt-1 flex items-center gap-1">
                <span
                  className={`text-[8px] font-medium px-1 rounded ${config.color} ${config.bg}/20`}
                >
                  {action.status.toUpperCase()}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 border-t border-zinc-800 px-3 py-2 bg-zinc-950">
        <div className="flex items-center justify-between text-[8px] text-zinc-500">
          <span>{actions.length} actions logged</span>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="h-1 w-1 rounded-full bg-emerald-500" />
              {successCount}
            </span>
            <span className="flex items-center gap-1">
              <span className="h-1 w-1 rounded-full bg-amber-500" />
              {pendingCount}
            </span>
            <span className="flex items-center gap-1">
              <span className="h-1 w-1 rounded-full bg-red-500" />
              {failedCount}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
