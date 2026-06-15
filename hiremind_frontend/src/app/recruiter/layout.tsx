import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";

export default function RecruiterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute roles={["recruiter", "admin"]}>
      <Navbar />
      <div className="mx-auto max-w-6xl px-4 py-8">{children}</div>
    </ProtectedRoute>
  );
}
