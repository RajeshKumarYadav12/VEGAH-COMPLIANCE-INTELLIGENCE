"use client";
import { useState, useEffect } from "react";
import {
  FiAlertTriangle,
  FiZap,
  FiX,
  FiRotateCcw,
  FiPieChart,
  FiFileText,
} from "react-icons/fi";
import { UploadZone } from "@/components/UploadZone";
import { AgentTimeline } from "@/components/AgentTimeline";
import { ComplianceMatrix } from "@/components/ComplianceMatrix";
import { ProposalViewer } from "@/components/ProposalViewer";
import { ModelToggle } from "@/components/ModelToggle";
import { useRFPStream } from "@/hooks/useRFPStream";
import { UploadedFiles, ModelProvider, ComplianceGap } from "@/types/rfp";
import { checkHealth } from "@/lib/api";

export default function Home() {
  const [files, setFiles] = useState<UploadedFiles>({
    rfpFile: null,
    capabilityFile: null,
  });
  const [model, setModel] = useState<ModelProvider>("claude");
  const [activeTab, setActiveTab] = useState<"compliance" | "proposal">(
    "compliance",
  );
  const [healthStatus, setHealthStatus] = useState<{
    capabilities_stored: number;
    status: string;
  } | null>(null);

  const {
    agents,
    isProcessing,
    pipelineResult,
    error,
    processRFP,
    abort,
    reset,
  } = useRFPStream();

  useEffect(() => {
    checkHealth()
      .then(setHealthStatus)
      .catch(() => setHealthStatus(null));
  }, []);

  useEffect(() => {
    if (pipelineResult) setActiveTab("proposal");
  }, [pipelineResult]);

  const canProcess = !!files.rfpFile && !isProcessing;
  const hasResult = !!pipelineResult;

  const handleProcess = () => {
    if (!files.rfpFile) return;
    processRFP(files.rfpFile, files.capabilityFile, model);
  };

  const handleReset = () => {
    if (!files.rfpFile) return;
    setActiveTab("compliance");
    processRFP(files.rfpFile, files.capabilityFile, model);
  };

  const gaps: ComplianceGap[] = pipelineResult?.reasoning?.gaps || [];
  const strongAlignments: string[] = pipelineResult?.reasoning?.strong_alignments || [];
  const overallScore = pipelineResult?.reasoning?.overall_compliance_score ?? 0;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header__inner">
          <div className="header__brand">
            <div className="header__logo">
              <svg viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="url(#logoGrad)" />
                <path
                  d="M8 22l6-12 4 8 3-5 3 9"
                  stroke="white"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <defs>
                  <linearGradient id="logoGrad" x1="0" y1="0" x2="32" y2="32">
                    <stop stopColor="#7c3aed" />
                    <stop offset="1" stopColor="#06b6d4" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div>
              <h1 className="header__title">VEGAH</h1>
              <p className="header__subtitle">Compliance Intelligence</p>
            </div>
          </div>
          <div className="header__status">
            {healthStatus && (
              <div className="health-indicator">
                <div
                  className={`health-dot ${healthStatus.status === "healthy" ? "health-dot--ok" : "health-dot--warn"}`}
                />
                <span className="health-text">
                  {healthStatus.status === "healthy" ? "Live" : "Degraded"} ·{" "}
                  {healthStatus.capabilities_stored} capabilities stored
                </span>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="main">
        {/* Left Panel */}
        <div className="panel panel--left">
          <div className="panel__section">
            <h2 className="panel__heading">
              <span className="panel__heading-num">01</span>Upload Documents
            </h2>
            <UploadZone onFilesSelected={setFiles} disabled={isProcessing} />
          </div>

          <div className="panel__section">
            <h2 className="panel__heading">
              <span className="panel__heading-num">02</span>Select AI Model
            </h2>
            <ModelToggle
              value={model}
              onChange={setModel}
              disabled={isProcessing}
            />
          </div>

          <div className="panel__section">
            <h2 className="panel__heading">
              <span className="panel__heading-num">03</span>Process
            </h2>
            {error && (
              <div className="error-alert">
                <FiAlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
            <div className="action-buttons">
              {!isProcessing && !hasResult && (
                <button
                  id="btn-process-rfp"
                  onClick={handleProcess}
                  disabled={!canProcess}
                  className="btn-primary"
                >
                  <FiZap className="w-5 h-5" />
                  Analyze RFP
                </button>
              )}
              {isProcessing && (
                <button onClick={abort} className="btn-danger">
                  <FiX className="w-5 h-5" />
                  Stop Processing
                </button>
              )}
              {hasResult && !isProcessing && (
                <button onClick={handleReset} className="btn-secondary">
                  <FiRotateCcw className="w-5 h-5" />
                  New Analysis
                </button>
              )}
            </div>
          </div>

          <div className="panel__section panel__section--grow">
            <AgentTimeline agents={agents} />
          </div>
        </div>

        {/* Right Panel */}
        <div className="panel panel--right">
          {!hasResult && !isProcessing && (
            <div className="empty-state">
              <div className="empty-state__icon">
                <svg viewBox="0 0 80 80" fill="none">
                  <circle
                    cx="40"
                    cy="40"
                    r="39"
                    stroke="url(#emptyGrad)"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                  />
                  <path
                    d="M25 50l10-20 8 15 5-8 7 13"
                    stroke="url(#emptyGrad2)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <defs>
                    <linearGradient
                      id="emptyGrad"
                      x1="0"
                      y1="0"
                      x2="80"
                      y2="80"
                    >
                      <stop stopColor="#7c3aed" stopOpacity="0.5" />
                      <stop offset="1" stopColor="#06b6d4" stopOpacity="0.5" />
                    </linearGradient>
                    <linearGradient
                      id="emptyGrad2"
                      x1="20"
                      y1="30"
                      x2="70"
                      y2="60"
                    >
                      <stop stopColor="#a78bfa" />
                      <stop offset="1" stopColor="#22d3ee" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
              <h2 className="empty-state__title">Ready to Analyze</h2>
              <p className="empty-state__desc">
                Upload your RFP PDF and optionally a capability matrix CSV, then
                click <strong>Analyze RFP</strong> to run the 6-agent pipeline.
              </p>
              <div className="empty-state__steps">
                {[
                  { n: "01", label: "Upload RFP PDF" },
                  { n: "02", label: "Add Capability Matrix (optional)" },
                  { n: "03", label: "Choose Reasoning AI Model" },
                  { n: "04", label: "Receive Executive Proposal" },
                ].map((s) => (
                  <div key={s.n} className="empty-step">
                    <span className="empty-step__num">{s.n}</span>
                    <span>{s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isProcessing && !hasResult && (
            <div className="processing-state">
              <div className="processing-state__animation">
                <div className="pulse-ring" />
                <div className="pulse-ring pulse-ring--2" />
                <div className="pulse-ring pulse-ring--3" />
                <div className="pulse-core">
                  <FiZap className="w-8 h-8 text-violet-400" />
                </div>
              </div>
              <h2 className="processing-state__title">Pipeline Running</h2>
              <p className="processing-state__desc">
                {agents.find((a) => a.status === "active")?.displayName ||
                  "Initializing pipeline"}{" "}
                is processing...
              </p>
            </div>
          )}

          {hasResult && pipelineResult && (
            <div className="results">
              <div className="results__tabs">
                <button
                  id="tab-compliance"
                  onClick={() => setActiveTab("compliance")}
                  className={`results-tab ${activeTab === "compliance" ? "results-tab--active" : ""}`}
                >
                  <FiPieChart className="w-4 h-4" />
                  Compliance Matrix
                </button>
                <button
                  id="tab-proposal"
                  onClick={() => setActiveTab("proposal")}
                  className={`results-tab ${activeTab === "proposal" ? "results-tab--active" : ""}`}
                >
                  <FiFileText className="w-4 h-4" />
                  Executive Proposal
                </button>
              </div>
              <div className="results__content">
                {activeTab === "compliance" && (
                  <ComplianceMatrix
                    gaps={gaps}
                    strongAlignments={strongAlignments}
                    overallScore={overallScore}
                  />
                )}
                {activeTab === "proposal" && (
                  <ProposalViewer proposal={pipelineResult.proposal} />
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
