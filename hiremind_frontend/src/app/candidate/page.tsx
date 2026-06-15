"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { AttemptSummary } from "@/types";

export default function CandidateDashboard() {
  const token = useAuthStore((s) => s.accessToken)!;
  const user = useAuthStore((s) => s.user);
  const [attempts, setAttempts] = useState<AttemptSummary[]>([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.myAttempts(token).then(setAttempts).finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-sans text-3xl font-extrabold">Candidate Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Welcome{user?.name ? `, ${user.name}` : ""}. Join an assessment or continue an attempt.
          </p>
        </div>
        <Link href="/candidate/analytics" className="btn-secondary">
          View Analytics
        </Link>
      </div>

      <div className="card-panel">
        <h2 className="font-sans text-lg font-bold">Join Assessment</h2>
        <p className="mt-2 text-sm text-muted">
          Enter the assessment ID from your recruiter, or use the invite link they shared.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <input
            className="input-field max-w-md"
            placeholder="Assessment UUID"
            value={assessmentId}
            onChange={(e) => setAssessmentId(e.target.value)}
          />
          {assessmentId && (
            <Link href={`/candidate/join/${assessmentId}`} className="btn-primary">
              Start Assessment
            </Link>
          )}
        </div>
      </div>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">My Attempts</h2>
        {loading ? (
          <p className="mt-4 text-muted">Loading...</p>
        ) : attempts.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No attempts yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="pb-3">Attempt</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Score</th>
                  <th className="pb-3">Started</th>
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <tr key={a.attempt_id} className="border-t border-border/60">
                    <td className="py-3 font-mono text-xs">{a.attempt_id.slice(0, 8)}...</td>
                    <td className="py-3">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="py-3">{a.total_score ?? "—"}</td>
                    <td className="py-3 text-muted">{formatDate(a.started_at)}</td>
                    <td className="py-3 text-right">
                      {a.status === "in_progress" && (
                        <Link
                          href={`/candidate/attempt/${a.attempt_id}?assessmentId=${a.assessment_id}`}
                          className="text-accent hover:underline"
                        >
                          Continue
                        </Link>
                      )}
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
