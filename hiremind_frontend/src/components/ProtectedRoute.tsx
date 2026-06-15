"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import type { UserRole } from "@/types";

export function ProtectedRoute({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: UserRole[];
}) {
  const router = useRouter();
  const { accessToken, role, hydrated } = useAuthStore();

  useEffect(() => {
    if (!hydrated) return;

    if (!accessToken) {
      router.replace("/login");
      return;
    }

    if (roles && role && !roles.includes(role)) {
      router.replace(role === "candidate" ? "/candidate" : "/recruiter");
    }
  }, [accessToken, role, hydrated, roles, router]);

  if (!hydrated || !accessToken) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted">
        Loading...
      </div>
    );
  }

  if (roles && role && !roles.includes(role)) {
    return null;
  }

  return <>{children}</>;
}
