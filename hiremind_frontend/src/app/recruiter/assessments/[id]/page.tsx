"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Assessment, Question } from "@/types";

export default function AssessmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.accessToken)!;
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const joinUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/candidate/join/${id}`
      : `/candidate/join/${id}`;

  useEffect(() => {
    async function load() {
      try {
        const [a, q] = await Promise.all([
          api.getAssessment(token, id),
          api.getQuestions(token, id),
        ]);
        setAssessment(a);
        setQuestions(q);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, id]);

  async function setStatus(status: string) {
    setActionMsg("");
    setError("");
    try {
      await api.updateAssessmentStatus(token, id, status);
      setAssessment((prev) => (prev ? { ...prev, status: status as Assessment["status"] } : prev));
      setActionMsg(`Assessment marked as ${status}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed");
    }
  }

  if (loading) return <p className="text-muted">Loading...</p>;
  if (!assessment) return <p className="text-red">{error || "Not found"}</p>;

  return (
    <div className="space-y-6">
      <Link href="/recruiter" className="text-sm text-muted hover:text-accent">
        ← Back
      </Link>

      <div className="card-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-sans text-2xl font-extrabold">{assessment.title}</h1>
            <p className="mt-1 text-sm text-muted">{assessment.role}</p>
            <div className="mt-3">
              <StatusBadge status={assessment.status} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {assessment.status === "draft" && (
              <button type="button" className="btn-primary" onClick={() => setStatus("active")}>
                Publish (Active)
              </button>
            )}
            {assessment.status === "active" && (
              <button type="button" className="btn-secondary" onClick={() => setStatus("archived")}>
                Archive
              </button>
            )}
          </div>
        </div>

        <div className="mt-6 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-lg bg-surface p-3">
            <p className="text-xs text-muted">Duration</p>
            <p>{assessment.duration_minutes} min</p>
          </div>
          <div className="rounded-lg bg-surface p-3">
            <p className="text-xs text-muted">Types</p>
            <p>{assessment.types.join(", ")}</p>
          </div>
          <div className="rounded-lg bg-surface p-3">
            <p className="text-xs text-muted">Questions</p>
            <p>{questions.length}</p>
          </div>
            <div className="rounded-lg bg-surface p-3">
              <p className="text-xs text-muted">Pass Score</p>
              <p>{assessment.pass_score ?? 0}%</p>
            </div>
            <div className="rounded-lg bg-surface p-3 col-span-2">
              <p className="text-xs text-muted">Section Cutoffs</p>
              <p>{assessment.section_cutoffs ? JSON.stringify(assessment.section_cutoffs) : "None"}</p>
            </div>
        </div>

        {assessment.status === "active" && (
          <div className="mt-6 rounded-lg border border-accent/20 bg-accent/5 p-4">
            <p className="text-xs uppercase tracking-wider text-accent">Candidate join link</p>
            <div className="mt-2 flex items-start gap-3">
              <p className="break-all text-sm max-w-[70%]">{joinUrl}</p>
              <div className="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(joinUrl);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    } catch {
                      // ignore
                    }
                  }}
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted">Share this link with candidates. They must be logged in as a candidate.</p>
          </div>
        )}

        {actionMsg && <p className="mt-4 text-sm text-green">{actionMsg}</p>}
        {error && <p className="mt-4 text-sm text-red">{error}</p>}
      </div>

      <section className="card-panel">
        <h2 className="font-sans text-lg font-bold">Questions ({questions.length})</h2>
        {questions.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No questions yet.</p>
        ) : (
          <div className="mt-4 space-y-4">
            {questions.map((q, i) => (
              <div key={q.id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-muted">Q{i + 1}</span>
                  <span className="badge border border-border text-accent">{q.type}</span>
                  <span className="badge border border-border text-gold">{q.difficulty}</span>
                  <span className="text-muted">{q.points} pts</span>
                </div>
                <div className="mt-2 text-sm max-h-28 overflow-auto whitespace-pre-wrap">{q.prompt}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
