import type {
  Assessment,
  AttemptSummary,
  CodeSubmitResult,
  Question,
  RecruiterAttempt,
  ProctorSummary,
  TokenResponse,
  User,
  UserRole,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function apiUrl(path = "") {
  return `${API_URL}${path}`;
}

export function wsUrl(path: string, token: string) {
  const base = API_URL.replace(/^http/, "ws");
  const joiner = path.includes("?") ? "&" : "?";
  return `${base}${path}${joiner}token=${encodeURIComponent(token)}`;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, String(detail));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  register(data: {
    name: string;
    email: string;
    password: string;
    role: UserRole;
  }) {
    return request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  login(data: { email: string; password: string }) {
    return request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  me(token: string) {
    return request<User>("/api/auth/me", {}, token);
  },

  refresh(refreshToken: string) {
    return request<TokenResponse>("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  listAssessments(token: string, status?: string) {
    const q = status ? `?status=${status}` : "";
    return request<Assessment[]>(`/api/assessments/list${q}`, {}, token);
  },

  getAssessment(token: string, id: string) {
    return request<Assessment>(`/api/assessments/${id}`, {}, token);
  },

  getQuestions(token: string, assessmentId: string) {
    return request<Question[]>(`/api/assessments/${assessmentId}/questions`, {}, token);
  },

  createAssessment(
    token: string,
    data: {
      title: string;
      role: string;
      types: string[];
      duration_minutes: number;
      proctoring: boolean;
      adaptive: boolean;
      start_date?: string;
      end_date?: string;
      proctoring_options?: Record<string, boolean>;
      section_cutoffs?: Record<string, number>;
      pass_score?: number;
    },
  ) {
    return request<Assessment>("/api/assessments/create", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  },

  updateAssessmentStatus(token: string, id: string, status: string) {
    return request<{ id: string; status: string }>(
      `/api/assessments/${id}/status?status=${status}`,
      { method: "PATCH" },
      token,
    );
  },

  generateQuestions(
    token: string,
    data: {
      role: string;
      skills: string[];
      difficulty: string;
      types: string[];
      count?: number;
      counts?: Record<string, number>;
      job_description?: string;
      experience_level?: string;
    },
    assessmentId?: string,
  ) {
    const q = assessmentId ? `?assessment_id=${assessmentId}` : "";
    return request<{ generated: number; questions?: unknown[] }>(
      `/api/ai/generate-questions${q}`,
      { method: "POST", body: JSON.stringify(data) },
      token,
    );
  },

  startAttempt(token: string, assessmentId: string) {
    return request<{
      attempt_id: string;
      assessment_id: string;
      duration_minutes: number;
      proctoring_enabled: boolean;
      status: string;
      started_at: string;
      resumed?: boolean;
    }>(`/api/attempts/start/${assessmentId}`, { method: "POST" }, token);
  },

  submitAnswers(
    token: string,
    attemptId: string,
    answers: { question_id: string; answer_index?: number; answer_text?: string }[],
  ) {
    return request(`/api/attempts/${attemptId}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }, token);
  },

  submitCode(
    token: string,
    data: {
      code: string;
      language: string;
      question_id: string;
      attempt_id: string;
    },
  ) {
    return request<CodeSubmitResult>("/api/code/submit", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  },

  submitAttempt(token: string, attemptId: string) {
    return request<{ attempt_id: string; status: string; submitted_at: string }>(
      `/api/attempts/${attemptId}/submit`,
      { method: "POST" },
      token,
    );
  },

  myAttempts(token: string) {
    return request<AttemptSummary[]>("/api/attempts/my", {}, token);
  },

  recruiterAttempts(token: string, assessmentId?: string) {
    const q = assessmentId ? `?assessment_id=${assessmentId}` : "";
    return request<RecruiterAttempt[]>(`/api/attempts/recruiter/all${q}`, {}, token);
  },

  evaluateAttempt(token: string, attemptId: string) {
    return request<{ attempt_id: string; evaluation_report: Record<string, unknown> }>(
      "/api/ai/evaluate",
      {
        method: "POST",
        body: JSON.stringify({ attempt_id: attemptId }),
      },
      token,
    );
  },

  adaptiveDifficulty(token: string, score: number) {
    return request<{ difficulty: string }>(`/api/ai/adaptive-difficulty`, {
      method: "POST",
      body: JSON.stringify({ score }),
    }, token);
  },

  logProctorEvent(
    token: string,
    data: {
      session_id: string;
      event_type: string;
      timestamp: string;
      metadata?: Record<string, unknown>;
      frame_snapshot?: string;
    },
  ) {
    return request("/api/proctor/event", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  },

  getReport(token: string, candidateId: string, format: "json" | "pdf" = "json") {
    if (format === "pdf") {
      return fetch(`${API_URL}/api/reports/${candidateId}?format=pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }
    return request(`/api/reports/${candidateId}?format=json`, {}, token);
  },

  getProctorSummary(token: string, attemptId: string) {
    return request<ProctorSummary>(`/api/proctor/session/${attemptId}/summary`, {}, token);
  },

  codeLanguages() {
    return request<{ languages: string[] }>("/api/code/languages");
  },
};
