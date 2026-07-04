import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
