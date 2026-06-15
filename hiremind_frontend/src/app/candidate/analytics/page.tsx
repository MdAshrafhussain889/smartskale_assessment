"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { AttemptSummary } from "@/types";

export default function CandidateAnalyticsPage() {
  const token = useAuthStore((s) => s.accessToken)!;
  const [attempts, setAttempts] = useState<AttemptSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.myAttempts(token).then(setAttempts).finally(() => setLoading(false));
  }, [token]);

  const stats = useMemo(() => {
    const scored = attempts.filter((attempt) => typeof attempt.total_score === "number");
    const average = scored.length
      ? scored.reduce((sum, attempt) => sum + Number(attempt.total_score), 0) / scored.length
      : null;
    return {
      total: attempts.length,
      inProgress: attempts.filter((attempt) => attempt.status === "in_progress").length,
      submitted: attempts.filter((attempt) => attempt.status === "submitted").length,
      evaluated: attempts.filter((attempt) => attempt.status === "evaluated").length,
      average,
      best: scored.length ? Math.max(...scored.map((attempt) => Number(attempt.total_score))) : null,
    };
  }, [attempts]);

  return (
    <div className="space-y-6">
      <Link href="/candidate" className="text-sm text-muted hover:text-accent">
        Back to dashboard
      </Link>

      <div>
        <h1 className="font-sans text-3xl font-extrabold">Candidate Analytics</h1>
        <p className="mt-1 text-sm text-muted">Track your assessment progress and scores.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Attempts</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-accent">{stats.total}</p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Evaluated</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-green">{stats.evaluated}</p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Average Score</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-purple">
            {stats.average === null ? "-" : stats.average.toFixed(1)}
          </p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Best Score</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-gold">
            {stats.best === null ? "-" : stats.best.toFixed(1)}
          </p>
        </div>
      </div>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">Status Breakdown</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-surface p-4">
            <p className="text-xs text-muted">In progress</p>
            <p className="mt-1 text-2xl font-bold text-accent">{stats.inProgress}</p>
          </div>
          <div className="rounded-lg bg-surface p-4">
            <p className="text-xs text-muted">Submitted</p>
            <p className="mt-1 text-2xl font-bold text-gold">{stats.submitted}</p>
          </div>
          <div className="rounded-lg bg-surface p-4">
            <p className="text-xs text-muted">Evaluated</p>
            <p className="mt-1 text-2xl font-bold text-green">{stats.evaluated}</p>
          </div>
        </div>
      </section>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">Recent Attempts</h2>
        {loading ? (
          <p className="mt-4 text-muted">Loading...</p>
        ) : attempts.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No attempt data yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="pb-3">Attempt</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Score</th>
                  <th className="pb-3">Started</th>
                  <th className="pb-3">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((attempt) => (
                  <tr key={attempt.attempt_id} className="border-t border-border/60">
                    <td className="py-3 font-mono text-xs">{attempt.attempt_id.slice(0, 8)}...</td>
                    <td className="py-3">
                      <StatusBadge status={attempt.status} />
                    </td>
                    <td className="py-3">{attempt.total_score ?? "-"}</td>
                    <td className="py-3 text-muted">{formatDate(attempt.started_at)}</td>
                    <td className="py-3 text-muted">{formatDate(attempt.submitted_at)}</td>
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
