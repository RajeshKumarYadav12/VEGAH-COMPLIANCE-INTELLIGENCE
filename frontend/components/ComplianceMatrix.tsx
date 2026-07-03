"use client";
import { ComplianceGap, RiskLevel } from "@/types/rfp";

interface ComplianceMatrixProps {
  gaps: ComplianceGap[];
  strongAlignments: string[];
  overallScore: number;
}

const riskConfig: Record<RiskLevel, { label: string; classes: string }> = {
  critical: { label: "CRITICAL", classes: "risk-badge risk-badge--critical" },
  high:     { label: "HIGH",     classes: "risk-badge risk-badge--high" },
  medium:   { label: "MEDIUM",   classes: "risk-badge risk-badge--medium" },
  low:      { label: "LOW",      classes: "risk-badge risk-badge--low" },
};

const gapTypeLabels: Record<string, string> = {
  missing_capability:     "Missing Capability",
  partial_match:          "Partial Match",
  compliance_risk:        "Compliance Risk",
  timeline_conflict:      "Timeline Conflict",
  certification_required: "Cert. Required",
};

function ScoreRing({ score }: { score: number }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 75 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="score-ring">
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={radius} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 55 55)"
          style={{ transition: "stroke-dashoffset 1s ease, stroke 0.5s ease" }}
        />
      </svg>
      <div className="score-ring__label">
        <span className="score-ring__value" style={{ color }}>{Math.round(score)}</span>
        <span className="score-ring__unit">%</span>
      </div>
    </div>
  );
}

export function ComplianceMatrix({ gaps, strongAlignments, overallScore }: ComplianceMatrixProps) {
  const criticalCount = gaps.filter((g) => g.risk_level === "critical").length;
  const highCount = gaps.filter((g) => g.risk_level === "high").length;
  const mediumCount = gaps.filter((g) => g.risk_level === "medium").length;
  const lowCount = gaps.filter((g) => g.risk_level === "low").length;

  return (
    <div className="compliance-matrix">
      {/* Header stats */}
      <div className="compliance-matrix__header">
        <div className="compliance-matrix__score-wrap">
          <ScoreRing score={overallScore} />
          <div>
            <h3 className="compliance-matrix__title">Compliance Score</h3>
            <p className="compliance-matrix__subtitle">
              {strongAlignments.length} strong alignments · {gaps.length} gaps identified
            </p>
          </div>
        </div>

        <div className="compliance-matrix__stats">
          <div className="stat-pill stat-pill--critical">
            <span className="stat-pill__count">{criticalCount}</span>
            <span>Critical</span>
          </div>
          <div className="stat-pill stat-pill--high">
            <span className="stat-pill__count">{highCount}</span>
            <span>High</span>
          </div>
          <div className="stat-pill stat-pill--medium">
            <span className="stat-pill__count">{mediumCount}</span>
            <span>Medium</span>
          </div>
          <div className="stat-pill stat-pill--low">
            <span className="stat-pill__count">{lowCount}</span>
            <span>Low</span>
          </div>
        </div>
      </div>

      {/* Gap table */}
      {gaps.length > 0 && (
        <div className="compliance-matrix__table-wrap">
          <table className="compliance-table">
            <thead>
              <tr>
                <th>Req. ID</th>
                <th>Gap Type</th>
                <th>Risk</th>
                <th>Description</th>
                <th>Matched Capability</th>
                <th>Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((gap) => (
                <tr key={gap.requirement_id} className="compliance-table__row">
                  <td>
                    <code className="req-id">{gap.requirement_id}</code>
                  </td>
                  <td>
                    <span className="gap-type-chip">
                      {gapTypeLabels[gap.gap_type] || gap.gap_type}
                    </span>
                  </td>
                  <td>
                    <span className={riskConfig[gap.risk_level]?.classes}>
                      {riskConfig[gap.risk_level]?.label}
                    </span>
                  </td>
                  <td className="compliance-table__description">{gap.description}</td>
                  <td>
                    {gap.matched_capability ? (
                      <div>
                        <div className="capability-name">{gap.matched_capability}</div>
                        {gap.match_score !== undefined && (
                          <div className="match-score-bar">
                            <div
                              className="match-score-bar__fill"
                              style={{ width: `${gap.match_score * 100}%` }}
                            />
                            <span className="match-score-bar__label">
                              {(gap.match_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-red-400 text-xs">None found</span>
                    )}
                  </td>
                  <td className="compliance-table__recommendation">{gap.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
