export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function dashboardPath(role: string | null) {
  if (role === "recruiter" || role === "admin") return "/recruiter";
  return "/candidate";
}
