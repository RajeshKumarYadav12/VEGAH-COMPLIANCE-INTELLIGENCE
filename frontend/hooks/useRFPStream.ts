"use client";
import { useState, useCallback, useRef } from "react";
import { AgentState, AgentEvent, PipelineResult, ModelProvider } from "@/types/rfp";
import { createRFPStream } from "@/lib/api";

const AGENT_DEFINITIONS: { name: string; displayName: string }[] = [
  { name: "Intake Agent", displayName: "Intake Agent" },
  { name: "Extraction Agent", displayName: "Extraction Agent" },
  { name: "RAG/Knowledge Agent", displayName: "RAG / Knowledge Agent" },
  { name: "Reasoning Agent", displayName: "Reasoning Agent" },
  { name: "Validator Agent", displayName: "Validator Agent" },
  { name: "Action Agent", displayName: "Action Agent" },
];

const initialAgents = (): AgentState[] =>
  AGENT_DEFINITIONS.map((a) => ({
    name: a.name,
    displayName: a.displayName,
    status: "pending",
    message: "Waiting...",
  }));

export function useRFPStream() {
  const [agents, setAgents] = useState<AgentState[]>(initialAgents());
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const updateAgent = useCallback((agentName: string, updates: Partial<AgentState>) => {
    setAgents((prev) =>
      prev.map((agent) =>
        agent.name === agentName || agent.displayName === agentName
          ? { ...agent, ...updates }
          : agent
      )
    );
  }, []);

  const processRFP = useCallback(
    async (
      rfpFile: File,
      capabilityFile: File | null,
      reasoningModel: ModelProvider
    ) => {
      // Reset state
      setAgents(initialAgents());
      setPipelineResult(null);
      setError(null);
      setIsProcessing(true);

      const { stream, abort } = createRFPStream(rfpFile, capabilityFile, reasoningModel);
      abortRef.current = abort;

      const reader = stream.getReader();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          try {
            const event: AgentEvent = JSON.parse(value);
            handleEvent(event);
          } catch {
            console.warn("Failed to parse SSE event:", value);
          }
        }
      } catch (err) {
        const msg = (err as Error).message || "Pipeline error";
        setError(msg);
      } finally {
        setIsProcessing(false);
        abortRef.current = null;
      }
    },
    [updateAgent]
  );

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      if (event.event_type === "pipeline_complete") {
        if (event.data?.proposal) {
          setPipelineResult(event.data as unknown as PipelineResult);
        }
        if (event.status === "error") {
          setError(event.message);
        }
        return;
      }

      const statusMap: Record<string, AgentState["status"]> = {
        agent_start: event.status === "active" ? "active" : "pending",
        agent_complete: "complete",
        agent_error: "error",
      };

      updateAgent(event.agent_name, {
        status: statusMap[event.event_type] ?? event.status,
        message: event.message,
        data: event.data,
        ...(event.event_type === "agent_start" && event.status === "active"
          ? { startTime: Date.now() }
          : {}),
        ...(event.event_type === "agent_complete" || event.event_type === "agent_error"
          ? { endTime: Date.now() }
          : {}),
      });
    },
    [updateAgent]
  );

  const abort = useCallback(() => {
    abortRef.current?.();
    setIsProcessing(false);
    setError("Processing aborted by user.");
  }, []);

  const reset = useCallback(() => {
    setAgents(initialAgents());
    setPipelineResult(null);
    setError(null);
    setIsProcessing(false);
  }, []);

  return {
    agents,
    isProcessing,
    pipelineResult,
    error,
    processRFP,
    abort,
    reset,
  };
}
