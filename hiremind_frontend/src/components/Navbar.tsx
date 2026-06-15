"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { dashboardPath } from "@/lib/utils";

export function Navbar() {
  const router = useRouter();
  const { accessToken, role, user, clearAuth } = useAuthStore();

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-bg/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="font-sans text-lg font-extrabold tracking-tight">
          Smart<span className="text-accent">Skale</span>
        </Link>

        <nav className="flex items-center gap-3 text-sm">
          {accessToken ? (
            <>
              <Link
                href={dashboardPath(role)}
                className="text-muted transition hover:text-accent"
              >
                Dashboard
              </Link>
              <span className="hidden text-muted sm:inline">
                {user?.name ?? "User"} · {role}
              </span>
              <button
                type="button"
                onClick={() => {
                  clearAuth();
                  router.push("/login");
                }}
                className="btn-secondary px-3 py-1.5 text-xs"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-muted transition hover:text-accent">
                Login
              </Link>
              <Link href="/register" className="btn-primary px-3 py-1.5 text-xs">
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
