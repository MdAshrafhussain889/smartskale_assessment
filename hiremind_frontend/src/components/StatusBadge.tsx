const styles: Record<string, string> = {
  draft: "bg-gold/10 text-gold border-gold/30",
  active: "bg-green/10 text-green border-green/30",
  archived: "bg-muted/10 text-muted border-border",
  in_progress: "bg-accent/10 text-accent border-accent/30",
  submitted: "bg-purple/10 text-purple border-purple/30",
  evaluated: "bg-green/10 text-green border-green/30",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`badge border ${styles[status] ?? "bg-surface text-muted border-border"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
