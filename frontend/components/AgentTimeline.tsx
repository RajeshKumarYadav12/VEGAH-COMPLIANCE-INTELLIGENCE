"use client";
import type { ReactNode } from "react";
import { AgentState } from "@/types/rfp";

interface AgentTimelineProps {
  agents: AgentState[];
}

const statusConfig: Record<string, { label: string; color: string; bg: string; icon: ReactNode }> = {
  pending: {
    label: "Waiting",
    color: "text-slate-400",
    bg: "bg-slate-800/50",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
  },
  active: {
    label: "Processing",
    color: "text-cyan-400",
    bg: "bg-cyan-950/60",
    icon: (
      <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path strokeLinecap="round" d="M12 3a9 9 0 110 18 9 9 0 010-18z" opacity="0.25" />
        <path strokeLinecap="round" d="M12 3a9 9 0 019 9" />
      </svg>
    ),
  },
  complete: {
    label: "Complete",
    color: "text-emerald-400",
    bg: "bg-emerald-950/60",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ),
  },
  error: {
    label: "Error",
    color: "text-red-400",
    bg: "bg-red-950/60",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  },
  skipped: {
    label: "Skipped",
    color: "text-slate-500",
    bg: "bg-slate-800/30",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M5 7l10 5-10 5V7z" />
      </svg>
    ),
  },
};

function AgentDataBadges({ data }: { data?: Record<string, unknown> }) {
  if (!data) return null;
  const entries = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined && v !== false && String(v) !== "0"
  );
  if (!entries.length) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {entries.slice(0, 4).map(([key, value]) => (
        <span key={key} className="agent-data-badge">
          <span className="agent-data-badge__key">{key.replace(/_/g, " ")}</span>
          <span className="agent-data-badge__value">{String(value)}</span>
        </span>
      ))}
    </div>
  );
}

function getDurationMs(agent: AgentState): string | null {
  if (!agent.startTime || !agent.endTime) return null;
  const ms = agent.endTime - agent.startTime;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AgentTimeline({ agents }: AgentTimelineProps) {
  return (
    <div className="agent-timeline">
      <h3 className="agent-timeline__title">
        Agent Pipeline
      </h3>

      <div className="agent-timeline__steps">
        {agents.map((agent, idx) => {
          const cfg = statusConfig[agent.status] || statusConfig.pending;
          const duration = getDurationMs(agent);

          return (
            <div key={agent.name} className="agent-step">
              {/* Connector line */}
              {idx < agents.length - 1 && (
                <div
                  className={`agent-step__connector ${
                    agent.status === "complete" ? "agent-step__connector--active" : ""
                  }`}
                />
              )}

              {/* Node */}
              <div className={`agent-step__node ${cfg.color} ${cfg.bg}`}>
                <div className={`agent-step__icon-wrap ${cfg.color}`}>
                  {cfg.icon}
                </div>
                <div className="agent-step__content">
                  <div className="agent-step__header">
                    <span className={`agent-step__name ${agent.status === "active" ? "animate-pulse" : ""}`}>
                      {agent.displayName}
                    </span>
                    <div className="flex items-center gap-2">
                      {duration && (
                        <span className="agent-step__duration">{duration}</span>
                      )}
                      <span className={`agent-step__status-badge ${cfg.color}`}>
                        {cfg.label}
                      </span>
                    </div>
                  </div>
                  {agent.message && agent.message !== "Waiting..." && (
                    <p className="agent-step__message">{agent.message}</p>
                  )}
                  <AgentDataBadges data={agent.data} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
