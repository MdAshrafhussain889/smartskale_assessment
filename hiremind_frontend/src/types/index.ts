export type UserRole = "candidate" | "recruiter" | "admin";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  role: UserRole;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Assessment {
  id: string;
  title: string;
  role: string;
  types: string[];
  duration_minutes: number;
  proctoring_enabled: boolean;
  adaptive: boolean;
  pass_score?: number | null;
  proctoring_options?: Record<string, boolean> | null;
  section_cutoffs?: Record<string, number> | null;
  status: "draft" | "active" | "archived";
  created_at: string;
}

export interface Question {
  id: string;
  type: "mcq" | "coding" | "sql" | "aptitude";
  difficulty: string;
  prompt: string;
  options?: string[] | null;
  test_cases?: { input?: string; expected_output?: string; stdin?: string; output?: string }[] | null;
  points: number;
  order: number;
}

export interface AttemptSummary {
  attempt_id: string;
  assessment_id: string;
  status: string;
  total_score: number | null;
  started_at: string | null;
  submitted_at: string | null;
}

export interface ProctorEvent {
  id?: string;
  event_id?: string;
  type?: string;
  event_type?: string;
  timestamp: string;
  snapshot_url?: string | null;
  metadata?: Record<string, unknown>;
  severity_weight?: number;
}

export interface ProctorSummary {
  attempt_id: string;
  total_events: number;
  event_counts: Record<string, number>;
  total_penalty_score: number;
  cheating_risk: "low" | "medium" | "high";
  events: ProctorEvent[];
}

export interface RecruiterAttempt {
  attempt_id: string;
  assessment_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  total_score: number | null;
  recommendation: string | null;
  submitted_at: string | null;
}

export interface CodeSubmitResult {
  passed_cases: number;
  total_cases: number;
  verdict: string;
  runtime_ms?: number | null;
  memory_kb?: number | null;
  failed_cases: {
    case: number;
    input: string;
    expected_output: string;
    actual_output: string;
    verdict: string;
  }[];
}
