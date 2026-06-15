"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function JoinAssessmentPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken)!;
  const [error, setError] = useState("");

  useEffect(() => {
    async function start() {
      try {
        const result = await api.startAttempt(token, assessmentId);
        router.replace(
          `/candidate/attempt/${result.attempt_id}?assessmentId=${assessmentId}`,
        );
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not start assessment. Is it active?",
        );
      }
    }
    start();
  }, [token, assessmentId, router]);

  if (error) {
    return (
      <div className="card-panel mx-auto max-w-lg text-center">
        <p className="text-red">{error}</p>
        <button
          type="button"
          className="btn-secondary mt-4"
          onClick={() => router.push("/candidate")}
        >
          Back to dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-[40vh] items-center justify-center text-muted">
      Starting assessment session...
    </div>
  );
}
