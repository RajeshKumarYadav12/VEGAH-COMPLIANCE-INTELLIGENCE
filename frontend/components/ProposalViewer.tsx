"use client";
import { useState } from "react";
import { ProposalResult } from "@/types/rfp";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ProposalViewerProps {
  proposal: ProposalResult;
}

export function ProposalViewer({ proposal }: ProposalViewerProps) {
  const [activeSection, setActiveSection] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(proposal.markdown_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPDF = async () => {
    setIsGeneratingPDF(true);
    try {
      // @ts-ignore
      const html2pdf = (await import("html2pdf.js")).default;
      const element = document.getElementById("proposal-pdf-content");
      if (!element) {
        throw new Error("Proposal content is not available for PDF export.");
      }

      const opt = {
        margin: 0,
        filename: `VEGAH_Proposal_${Date.now()}.pdf`,
        image: { type: "jpeg" as const, quality: 1.0 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          logging: false,
          backgroundColor: "#ffffff",
          scrollY: 0,
        },
        jsPDF: {
          unit: "mm" as const,
          format: "a4" as const,
          orientation: "portrait" as const,
        },
        pagebreak: { mode: ["avoid-all", "css", "legacy"] as const },
      };

      await html2pdf().set(opt).from(element).save();
    } catch (err) {
      console.error("PDF generation failed:", err);
    } finally {
      setIsGeneratingPDF(false);
    }
  };

  const handleDownload = (format: "md" | "txt") => {
    const blob = new Blob([proposal.markdown_content], {
      type: format === "md" ? "text/markdown" : "text/plain",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `VEGAH_Proposal_${Date.now()}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="proposal-viewer">
      {/* Toolbar */}
      <div className="proposal-viewer__toolbar">
        <div className="proposal-viewer__meta">
          <h3 className="proposal-viewer__title">{proposal.proposal_title}</h3>
          <div className="proposal-viewer__meta-badges">
            <span className="meta-badge">
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2a10 10 0 110 20A10 10 0 0112 2zm1 5h-2v6l5.25 3.15.75-1.23-4-2.42V7z" />
              </svg>
              {new Date(proposal.generated_at).toLocaleString()}
            </span>
            <span className="meta-badge">
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z" />
              </svg>
              {proposal.model_used.includes("claude")
                ? "Claude 3.5 Sonnet"
                : "GPT-4o"}
            </span>
            <span className="meta-badge">
              {proposal.word_count.toLocaleString()} words
            </span>
            <span
              className={`meta-badge ${proposal.overall_score >= 75 ? "meta-badge--success" : proposal.overall_score >= 50 ? "meta-badge--warning" : "meta-badge--danger"}`}
            >
              {proposal.overall_score.toFixed(1)}% compliance
            </span>
          </div>
        </div>

        <div className="proposal-viewer__actions">
          <button
            onClick={handleCopy}
            className="btn-icon"
            title="Copy markdown"
          >
            {copied ? (
              <svg
                className="w-4 h-4 text-emerald-400"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M19.916 4.626a.75.75 0 01.208 1.04l-9 13.5a.75.75 0 01-1.154.114l-6-6a.75.75 0 011.06-1.06l5.353 5.353 8.493-12.739a.75.75 0 011.04-.208z"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
            {copied ? "Copied!" : "Copy"}
          </button>
          <button onClick={() => handleDownload("md")} className="btn-icon">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Download .md
          </button>
          <button onClick={() => handleDownload("txt")} className="btn-icon">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Download .txt
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={isGeneratingPDF}
            className="btn-icon"
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {isGeneratingPDF ? "Generating..." : "Download PDF"}
          </button>
        </div>
      </div>

      {/* Section nav */}
      {proposal.sections.length > 0 && (
        <div className="proposal-viewer__nav">
          {proposal.sections.map((section, idx) => (
            <button
              key={idx}
              onClick={() =>
                setActiveSection(activeSection === idx ? null : idx)
              }
              className={`section-nav-btn ${activeSection === idx ? "section-nav-btn--active" : ""}`}
            >
              {section.title}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div
        id="proposal-pdf-content"
        className={`proposal-viewer__content ${isGeneratingPDF ? "pdf-export-mode" : ""}`}
      >
        {/* PDF Header - Visible primarily when exported, but looks great in UI too */}
        <div className="mb-10 border-b border-slate-800 pb-8 mt-4 pdf-header">
          <h1 className="text-4xl font-extrabold text-white mb-6 leading-tight pdf-title">
            {proposal.proposal_title}
          </h1>
          <div className="flex flex-wrap gap-3">
            <span className="px-3 py-1.5 bg-slate-900 border border-slate-700 text-slate-300 rounded-md text-sm font-medium">
              Generated: {new Date(proposal.generated_at).toLocaleString()}
            </span>
            <span className="px-3 py-1.5 bg-slate-900 border border-slate-700 text-slate-300 rounded-md text-sm font-medium">
              Model: {proposal.model_used}
            </span>
            <span className="px-3 py-1.5 bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 rounded-md text-sm font-bold">
              {proposal.overall_score.toFixed(1)}% Compliance Alignment
            </span>
            <span className="px-3 py-1.5 bg-indigo-950/40 border border-indigo-500/30 text-indigo-400 rounded-md text-sm font-medium">
              VEGAH Proprietary & Confidential
            </span>
          </div>
        </div>

        <div className="prose-container">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => <h1 className="md-h1">{children}</h1>,
              h2: ({ children }) => <h2 className="md-h2">{children}</h2>,
              h3: ({ children }) => <h3 className="md-h3">{children}</h3>,
              p: ({ children }) => <p className="md-p">{children}</p>,
              ul: ({ children }) => <ul className="md-ul">{children}</ul>,
              ol: ({ children }) => <ol className="md-ol">{children}</ol>,
              li: ({ children }) => <li className="md-li">{children}</li>,
              strong: ({ children }) => (
                <strong className="md-strong">{children}</strong>
              ),
              em: ({ children }) => <em className="md-em">{children}</em>,
              code: ({ children }) => (
                <code className="md-code">{children}</code>
              ),
              table: ({ children }) => (
                <div className="md-table-wrap">
                  <table className="md-table">{children}</table>
                </div>
              ),
              th: ({ children }) => <th className="md-th">{children}</th>,
              td: ({ children }) => <td className="md-td">{children}</td>,
              blockquote: ({ children }) => (
                <blockquote className="md-blockquote">{children}</blockquote>
              ),
              hr: () => <hr className="md-hr" />,
            }}
          >
            {proposal.markdown_content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
