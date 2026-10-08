import { Navigate } from "react-router-dom";

import { LoginForm } from "@/features/auth/LoginForm";
import { useAuth } from "@/features/auth/AuthContext";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-ink-muted">
        Loading…
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-lg font-semibold text-white">
            M
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">MailFlow</h1>
          <p className="mt-1 text-sm text-ink-muted">Sign in to your campaign dashboard</p>
        </div>

        <div className="card p-6 sm:p-8">
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
