"use client";

import { useEffect, useState } from "react";

type Cluster = {
  cluster_id: number;
  theme_label: string;
  reach_count: number;
  rice_score: number;
  adjusted_score: number;
  is_severity_override: boolean;
  justification: string;
  impact: number;
  confidence: number;
  effort: number;
  prd: { problem_statement?: string; proposed_solution?: string; success_metric?: string } | null;
};

export default function Home() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/clusters")
      .then((res) => {
        if (!res.ok) throw new Error("Backend returned " + res.status);
        return res.json();
      })
      .then((data) => {
        setClusters(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="font-mono text-sm" style={{ color: "var(--muted)" }}>Loading priority intelligence...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="font-mono text-sm" style={{ color: "var(--brick)" }}>
          Could not reach backend: {error}. Is uvicorn running on :8000?
        </p>
      </main>
    );
  }

  const [top, ...rest] = clusters;

  return (
    <div className="min-h-screen flex">
      <aside
        className="w-56 shrink-0 p-6 border-r"
        style={{ borderColor: "var(--line)" }}
      >
        <h2 className="font-display text-2xl mb-8" style={{ color: "var(--ink)" }}>Catalyst</h2>
        <nav className="flex flex-col gap-1">
          <a className="px-3 py-2 rounded-md text-sm font-medium" style={{ background: "var(--ink)", color: "var(--paper)" }}>
            Triage
          </a>
          <a href="/approvals" className="px-3 py-2 rounded-md text-sm" style={{ color: "var(--muted)" }}>Approval Queue</a>
          <a className="px-3 py-2 rounded-md text-sm" style={{ color: "var(--muted)" }}>
            Activity Log
          </a>
        </nav>
      </aside>

      <main className="flex-1 p-12 max-w-4xl">
        {top && (
          <section className="mb-12 pb-10 border-b" style={{ borderColor: "var(--line)" }}>
            <div className="flex items-baseline gap-3 mb-3">
              <span className="font-mono text-sm" style={{ color: "var(--muted)" }}>TOP PRIORITY</span>
              {top.is_severity_override && (
                <span
                  className="font-mono text-xs px-2 py-0.5 rounded"
                  style={{ background: "var(--brick)", color: "var(--paper)" }}
                >
                  SECURITY / COMPLIANCE
                </span>
              )}
            </div>
            <h1 className="font-display text-4xl mb-4 leading-tight" style={{ color: "var(--ink)" }}>
              {top.theme_label}
            </h1>
            <div className="flex items-end gap-8 mb-4">
              <div>
                <div className="font-mono text-6xl" style={{ color: "var(--ochre)" }}>
                  {top.adjusted_score.toFixed(0)}
                </div>
                <div className="font-mono text-xs" style={{ color: "var(--muted)" }}>PRIORITY SCORE</div>
              </div>
              <div>
                <div className="font-mono text-2xl" style={{ color: "var(--ink)" }}>{top.reach_count}</div>
                <div className="font-mono text-xs" style={{ color: "var(--muted)" }}>REPORTS</div>
              </div>
            </div>
            <p className="text-base mb-4" style={{ color: "var(--ink)" }}>{top.justification}</p>
            {top.prd?.proposed_solution && (
              <p className="text-sm italic" style={{ color: "var(--teal)" }}>
                Proposed: {top.prd.proposed_solution}
              </p>
            )}
          </section>
        )}

        <div>
          <h3 className="font-mono text-xs mb-4" style={{ color: "var(--muted)" }}>
            REMAINING PRIORITIES ({rest.length})
          </h3>
          {rest.map((c, i) => (
            <div
              key={c.cluster_id}
              className="flex items-center gap-4 py-4 border-b"
              style={{ borderColor: "var(--line)" }}
            >
              <span className="font-mono text-sm w-6" style={{ color: "var(--muted)" }}>{i + 2}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span style={{ color: "var(--ink)" }}>{c.theme_label}</span>
                  {c.is_severity_override && (
                    <span
                      className="font-mono text-xs px-1.5 py-0.5 rounded"
                      style={{ background: "var(--brick)", color: "var(--paper)" }}
                    >
                      SEC
                    </span>
                  )}
                </div>
                <div className="font-mono text-xs mt-1" style={{ color: "var(--muted)" }}>
                  {c.reach_count} reports Â· impact {c.impact} Â· effort {c.effort}
                </div>
              </div>
              <span className="font-mono text-lg" style={{ color: "var(--ochre)" }}>
                {c.adjusted_score.toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}