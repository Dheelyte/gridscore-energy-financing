import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { DEMO_ACCOUNTS, DEMO_PASSWORD, type DemoAccount } from "@/lib/demoAccounts";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const signIn = async (creds: { email: string; password: string }, landing: string) => {
    setBusy(creds.email);
    setError(null);
    try {
      await login(creds.email, creds.password);
      navigate(landing);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(null);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    void signIn({ email, password }, "/console");
  };

  const quickLogin = (acct: DemoAccount) =>
    void signIn({ email: acct.email, password: acct.password }, acct.landing);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-1 flex items-center gap-2 font-mono text-sm font-semibold">
            <img src="/grid.svg" alt="" className="h-6 w-6" />
            GridScore<span className="text-primary">AI</span>
          </div>
          <CardTitle>Sign in</CardTitle>
          <p className="text-xs text-muted-foreground">
            Shared credit scoring for Africa&apos;s PAYG energy lenders.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <Input
              type="email"
              placeholder="Email"
              aria-label="Email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              type="password"
              placeholder="Password"
              aria-label="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy !== null}>
              {busy !== null && <Loader2 className="h-4 w-4 animate-spin" />} Sign in
            </Button>
          </form>

          {/* Judge-friendly one-click role logins (synthetic demo accounts). */}
          <div className="mt-6">
            <div className="flex items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">
                Demo logins for judges
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>
            <div className="mt-3 space-y-2">
              {DEMO_ACCOUNTS.map((acct) => (
                <button
                  key={acct.email}
                  type="button"
                  onClick={() => quickLogin(acct)}
                  disabled={busy !== null}
                  aria-label={`Enter as ${acct.label}`}
                  className="flex w-full items-center justify-between gap-3 rounded-md border border-border bg-card px-3 py-2 text-left transition-colors hover:bg-secondary disabled:pointer-events-none disabled:opacity-50"
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{acct.label}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {acct.blurb}
                    </span>
                  </span>
                  {busy === acct.email ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                  ) : (
                    <span className="shrink-0 text-xs font-medium text-primary">Enter →</span>
                  )}
                </button>
              ))}
            </div>
            <p className="mt-3 text-center text-[0.7rem] text-muted-foreground">
              All demo accounts use the password{" "}
              <code className="rounded bg-secondary px-1 py-0.5">{DEMO_PASSWORD}</code>
            </p>
          </div>

          <p className="mt-4 text-center text-[0.7rem] text-muted-foreground">
            Synthetic data only · pre-production prototype
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
