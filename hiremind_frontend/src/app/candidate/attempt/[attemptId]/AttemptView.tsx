"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CodeEditor } from "@/components/CodeEditor";
import { StatusBadge } from "@/components/StatusBadge";
import { useProctoring } from "@/hooks/useProctoring";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Assessment, CodeSubmitResult, Question } from "@/types";

export default function AttemptView() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const searchParams = useSearchParams();
  const assessmentId = searchParams.get("assessmentId") ?? "";
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken)!;

  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [codeByQuestion, setCodeByQuestion] = useState<Record<string, string>>({});
  const [codeLang, setCodeLang] = useState("python");
  const [codeResults, setCodeResults] = useState<Record<string, CodeSubmitResult>>({});
  const [activeIndex, setActiveIndex] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [runningCode, setRunningCode] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const { videoRef, state: proctorState } = useProctoring(
    assessment?.proctoring_enabled ?? false,
    attemptId,
    token,
  );

  useEffect(() => {
    if (!assessmentId) {
      setError("Missing assessment ID");
      setLoading(false);
      return;
    }

    async function load() {
      try {
        const [a, q] = await Promise.all([
          api.getAssessment(token, assessmentId),
          api.getQuestions(token, assessmentId),
        ]);
        setAssessment(a);
        const sorted = q.sort((x, y) => x.order - y.order);
        setQuestions(sorted);
        // If assessment is adaptive, try to set the initial active question based on adaptive difficulty
        if (a.adaptive) {
          try {
            const resp = await api.adaptiveDifficulty(token, 0);
            const desired = resp.difficulty;
            const idx = sorted.findIndex((qq) => qq.difficulty === desired);
            if (idx >= 0) setActiveIndex(idx);
          } catch {
            // ignore adaptive errors and fall back to first question
          }
        }
        setSecondsLeft(a.duration_minutes * 60);

        const initialCode: Record<string, string> = {};
        q.forEach((question) => {
          if (question.type === "coding" || question.type === "sql") {
            initialCode[question.id] =
              question.type === "sql"
                ? "-- Write your SQL query here\nSELECT 1;"
                : "# Write your solution here\n";
          }
        });
        setCodeByQuestion(initialCode);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load assessment");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [token, assessmentId]);

  useEffect(() => {
    if (secondsLeft === null || done || secondsLeft <= 0) return;
    const timer = setInterval(() => {
      setSecondsLeft((s) => (s !== null && s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsLeft, done]);

  const handleFinalSubmit = useCallback(async () => {
    setSubmitting(true);
    setError("");
    try {
      const mcqItems = questions
        .filter((q) => (q.type === "mcq" || q.type === "aptitude") && answers[q.id] !== undefined)
        .map((q) => ({
          question_id: q.id,
          answer_index: answers[q.id],
        }));

      if (mcqItems.length > 0) {
        await api.submitAnswers(token, attemptId, mcqItems);
      }

      await api.submitAttempt(token, attemptId);
      setDone(true);
      router.push("/candidate");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  }, [answers, attemptId, questions, router, token]);

  useEffect(() => {
    if (secondsLeft === 0 && !done && !submitting) {
      handleFinalSubmit();
    }
  }, [secondsLeft, done, submitting, handleFinalSubmit]);

  const activeQuestion = questions[activeIndex];
  const timerLabel = useMemo(() => {
    if (secondsLeft === null) return "--:--";
    const m = Math.floor(secondsLeft / 60);
    const s = secondsLeft % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  }, [secondsLeft]);

  async function saveMcqAnswer(questionId: string, index: number) {
    setAnswers((prev) => ({ ...prev, [questionId]: index }));
    try {
      await api.submitAnswers(token, attemptId, [
        { question_id: questionId, answer_index: index },
      ]);
    } catch {
      // saved locally; will batch on final submit
    }
  }

  async function runCode(question: Question) {
    const code = codeByQuestion[question.id] ?? "";
    setRunningCode(true);
    setError("");
    try {
      const lang = question.type === "sql" ? "sql" : codeLang;
      const result = await api.submitCode(token, {
        code,
        language: lang,
        question_id: question.id,
        attempt_id: attemptId,
      });
      setCodeResults((prev) => ({ ...prev, [question.id]: result }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Code execution failed");
    } finally {
      setRunningCode(false);
    }
  }

  async function getNextAdaptiveIndex() {
    // compute a simple proxy score from code runs: average pass ratio (0-100)
    const runs = Object.entries(codeResults || {});
    if (runs.length === 0) return Math.min(activeIndex + 1, questions.length - 1);
    let totalRatio = 0;
    let count = 0;
    for (const [, r] of runs) {
      if (r.total_cases && r.total_cases > 0) {
        totalRatio += (r.passed_cases || 0) / r.total_cases;
        count += 1;
      }
    }
    const avg = count > 0 ? (totalRatio / count) * 100.0 : 0;
    try {
      const resp = await api.adaptiveDifficulty(token, avg);
      const desired = resp.difficulty;
      // choose the next unanswered question with that difficulty
      const seen = new Set<string>([...Object.keys(answers), ...Object.keys(codeResults)]);
      const idx = questions.findIndex((q) => !seen.has(q.id) && q.difficulty === desired);
      if (idx >= 0) return idx;
    } catch {
      // fall through
    }
    return Math.min(activeIndex + 1, questions.length - 1);
  }

  if (loading) {
    return <p className="text-muted">Loading assessment...</p>;
  }

  if (error && !assessment) {
    return <p className="text-red">{error}</p>;
  }

  if (done) {
    return (
      <div className="card-panel mx-auto max-w-lg text-center">
        <h1 className="font-sans text-2xl font-extrabold text-green">Submitted!</h1>
        <p className="mt-2 text-sm text-muted">Your attempt has been recorded.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="card-panel flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-sans text-xl font-extrabold">{assessment?.title}</h1>
          <p className="text-sm text-muted">{assessment?.role}</p>
        </div>
        <div className="flex items-center gap-4">
          {assessment?.proctoring_enabled && (
            <span className="badge border border-red/30 bg-red/10 text-red">
              Proctored
            </span>
          )}
          <div className="text-right">
            <p className="text-xs text-muted">Time left</p>
            <p className={`font-sans text-2xl font-extrabold ${secondsLeft !== null && secondsLeft < 300 ? "text-red" : "text-accent"}`}>
              {timerLabel}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <aside className="card-panel h-fit space-y-4">
          <p className="text-xs uppercase tracking-wider text-muted">Questions</p>
          <ul className="mt-3 space-y-2">
            {questions.map((q, i) => (
              <li key={q.id}>
                <button
                  type="button"
                  onClick={() => setActiveIndex(i)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                    i === activeIndex
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border text-muted hover:border-accent/30"
                  }`}
                >
                  Q{i + 1} · {q.type}
                </button>
              </li>
            ))}
          </ul>

          {assessment?.proctoring_enabled && (
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-wider text-muted">Webcam</p>
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    proctorState.cameraReady ? "bg-green" : "bg-red"
                  }`}
                />
              </div>
              <video
                ref={videoRef}
                muted
                playsInline
                className="mt-3 aspect-video w-full rounded border border-border bg-bg object-cover"
              />
              <div className="mt-3 space-y-1 text-xs text-muted">
                <p>Face: {proctorState.faceCount === null ? "checking" : proctorState.faceCount}</p>
                <p>Detector: {proctorState.detectorReady ? "active" : "fallback"}</p>
                <p>Eye signal: {proctorState.eyeSignal}</p>
                {proctorState.error && <p className="text-gold">{proctorState.error}</p>}
              </div>
            </div>
          )}
        </aside>

        <section className="card-panel">
          {activeQuestion ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={activeQuestion.type} />
                <span className="text-xs text-muted">{activeQuestion.points} points</span>
              </div>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed">
                {activeQuestion.prompt}
              </p>

              {(activeQuestion.type === "mcq" || activeQuestion.type === "aptitude") &&
                activeQuestion.options && (
                  <div className="mt-6 space-y-2">
                    {activeQuestion.options.map((opt, idx) => (
                      <label
                        key={idx}
                        className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 transition ${
                          answers[activeQuestion.id] === idx
                            ? "border-accent bg-accent/10"
                            : "border-border hover:border-accent/30"
                        }`}
                      >
                        <input
                          type="radio"
                          name={activeQuestion.id}
                          checked={answers[activeQuestion.id] === idx}
                          onChange={() => saveMcqAnswer(activeQuestion.id, idx)}
                        />
                        <span className="text-sm">{opt}</span>
                      </label>
                    ))}
                  </div>
                )}

              {(activeQuestion.type === "coding" || activeQuestion.type === "sql") && (
                <div className="mt-6 space-y-4">
                  {activeQuestion.type === "coding" && (
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-muted">Language</label>
                      <select
                        className="input-field max-w-[160px]"
                        value={codeLang}
                        onChange={(e) => setCodeLang(e.target.value)}
                      >
                        {["python", "java", "cpp", "js"].map((l) => (
                          <option key={l} value={l}>
                            {l}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <CodeEditor
                    language={activeQuestion.type === "sql" ? "sql" : codeLang}
                    value={codeByQuestion[activeQuestion.id] ?? ""}
                    onChange={(v) =>
                      setCodeByQuestion((prev) => ({ ...prev, [activeQuestion.id]: v }))
                    }
                  />
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={runningCode}
                    onClick={() => runCode(activeQuestion)}
                  >
                    {runningCode ? "Running..." : "Run & Submit Code"}
                  </button>
                  {codeResults[activeQuestion.id] && (
                    <div className="rounded-lg border border-border bg-surface p-4 text-sm">
                      <p>
                        Verdict:{" "}
                        <span className="text-accent">
                          {codeResults[activeQuestion.id].verdict}
                        </span>
                      </p>
                      <p className="text-muted">
                        Passed {codeResults[activeQuestion.id].passed_cases}/
                        {codeResults[activeQuestion.id].total_cases} test cases
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-muted">No questions in this assessment.</p>
          )}

          {error && <p className="mt-4 text-sm text-red">{error}</p>}

          <div className="mt-8 flex flex-wrap justify-between gap-3 border-t border-border pt-6">
            <button
              type="button"
              className="btn-secondary"
              disabled={activeIndex === 0}
              onClick={() => setActiveIndex((i) => Math.max(0, i - 1))}
            >
              Previous
            </button>
            <div className="flex gap-2">
              {activeIndex < questions.length - 1 ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={async () => {
                    if (assessment?.adaptive) {
                      setActiveIndex(await getNextAdaptiveIndex());
                    } else {
                      setActiveIndex((i) => i + 1);
                    }
                  }}
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-primary"
                  disabled={submitting}
                  onClick={handleFinalSubmit}
                >
                  {submitting ? "Submitting..." : "Submit Assessment"}
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
