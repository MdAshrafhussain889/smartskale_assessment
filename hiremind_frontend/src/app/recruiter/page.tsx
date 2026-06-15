"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { Assessment, RecruiterAttempt } from "@/types";

const recommendationStyles: Record<string, string> = {
  strong_hire: "border-green/30 bg-green/10 text-green",
  hire: "border-accent/30 bg-accent/10 text-accent",
  borderline: "border-gold/30 bg-gold/10 text-gold",
  no_hire: "border-red/30 bg-red/10 text-red",
};

function recommendationLabel(value: string | null) {
  if (!value) return "—";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function RecruiterDashboard() {
  const token = useAuthStore((s) => s.accessToken)!;
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [attempts, setAttempts] = useState<RecruiterAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluatingId, setEvaluatingId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [a, t] = await Promise.all([
          api.listAssessments(token),
          api.recruiterAttempts(token),
        ]);
        setAssessments(a);
        setAttempts(t);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  async function evaluate(attemptId: string) {
    setEvaluatingId(attemptId);
    try {
      await api.evaluateAttempt(token, attemptId);
      const updated = await api.recruiterAttempts(token);
      setAttempts(updated);
    } finally {
      setEvaluatingId(null);
    }
  }

  if (loading) {
    return <p className="text-muted">Loading dashboard...</p>;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-sans text-3xl font-extrabold">Recruiter Dashboard</h1>
          <p className="mt-1 text-sm text-muted">Manage assessments and review candidates</p>
        </div>
        <Link href="/recruiter/assessments/new" className="btn-primary">
          + New Assessment
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Assessments</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-accent">
            {assessments.length}
          </p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Total Attempts</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-green">
            {attempts.length}
          </p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Evaluated</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-purple">
            {attempts.filter((a) => a.status === "evaluated").length}
          </p>
        </div>
      </div>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">Your Assessments</h2>
        {assessments.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No assessments yet. Create your first one.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="pb-3">Title</th>
                  <th className="pb-3">Role</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Created</th>
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {assessments.map((a) => (
                  <tr key={a.id} className="border-t border-border/60">
                    <td className="py-3">{a.title}</td>
                    <td className="py-3 text-muted">{a.role}</td>
                    <td className="py-3">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="py-3 text-muted">{formatDate(a.created_at)}</td>
                    <td className="py-3 text-right">
                      <Link
                        href={`/recruiter/assessments/${a.id}`}
                        className="text-accent hover:underline"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">Recent Attempts</h2>
        {attempts.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No candidate attempts yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="pb-3">Candidate</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Score</th>
                  <th className="pb-3">Recommendation</th>
                  <th className="pb-3">Submitted</th>
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {attempts.slice(0, 10).map((a) => (
                  <tr key={a.attempt_id} className="border-t border-border/60">
                    <td className="py-3">
                      <div>{a.candidate_name}</div>
                      <div className="text-xs text-muted">{a.candidate_email}</div>
                    </td>
                    <td className="py-3">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="py-3">{a.total_score ?? "—"}</td>
                    <td className="py-3">
                      {a.recommendation ? (
                        <span
                          className={`badge border ${
                            recommendationStyles[a.recommendation] ??
                            "border-border bg-surface text-muted"
                          }`}
                        >
                          {recommendationLabel(a.recommendation)}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="py-3 text-muted">{formatDate(a.submitted_at)}</td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-3">
                        <Link
                          href={`/recruiter/proctor/${a.attempt_id}`}
                          className="text-xs text-muted hover:text-accent"
                        >
                          Live Proctor
                        </Link>
                      {a.status === "submitted" && (
                        <button
                          type="button"
                          className="text-xs text-accent hover:underline"
                          disabled={evaluatingId === a.attempt_id}
                          onClick={() => evaluate(a.attempt_id)}
                        >
                          {evaluatingId === a.attempt_id ? "Evaluating..." : "AI Evaluate"}
                        </button>
                      )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
