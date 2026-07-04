import { Activity, Network, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ApiState = "checking" | "online" | "offline";

/** Landing page for the Stage 0 skeleton. Pings the backend so the wired
 *  full-stack (frontend -> API) is visible at a glance. */
export default function App() {
  const [api, setApi] = useState<ApiState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE_URL}/health`, { signal: controller.signal })
      .then((r) => setApi(r.ok ? "online" : "offline"))
      .catch(() => setApi("offline"));
    return () => controller.abort();
  }, []);

  return (
    <main className="min-h-dvh bg-background">
      <div className="mx-auto flex min-h-dvh max-w-5xl flex-col px-6 py-10">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono text-sm font-semibold tracking-tight">
            <img src="/grid.svg" alt="" className="h-7 w-7" />
            GridScore<span className="text-primary">AI</span>
          </div>
          <ApiBadge state={api} />
        </header>

        <section className="flex flex-1 flex-col justify-center py-16">
          <span className="mb-4 inline-flex w-fit items-center rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            Synthetic data only · pre-production prototype
          </span>
          <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            The credit infrastructure for{" "}
            <span className="text-primary">Africa&apos;s energy lenders</span>.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            A shared PAYG repayment data cooperative. Operators contribute anonymised histories and
            receive an Energy Credit Score sharper than any single operator could compute alone.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="/console">
              <Button size="lg">Open the operator console</Button>
            </a>
            <a href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">
              <Button size="lg" variant="outline">
                API docs
              </Button>
            </a>
          </div>

          <div className="mt-16 grid gap-4 sm:grid-cols-3">
            <FeatureCard
              icon={<Network className="h-5 w-5 text-primary" />}
              title="Cooperative network effect"
              body="Solo view vs pooled view — the pooled score is measurably more confident."
            />
            <FeatureCard
              icon={<ShieldCheck className="h-5 w-5 text-primary" />}
              title="Privacy by design"
              body="No raw PII. Identities are salted hashes; every access is audited."
            />
            <FeatureCard
              icon={<Activity className="h-5 w-5 text-primary" />}
              title="Honest, explainable ML"
              body="Realistic metrics and SHAP-driven top factors behind every decision."
            />
          </div>
        </section>

        <footer className="border-t border-border pt-6 text-xs text-muted-foreground">
          Synthetic-data prototype · sign in for the guided tour. © {new Date().getFullYear()}{" "}
          GridScore AI.
        </footer>
      </div>
    </main>
  );
}

function ApiBadge({ state }: { state: ApiState }) {
  const label = { checking: "Checking API…", online: "API online", offline: "API offline" }[state];
  const dot = {
    checking: "bg-muted-foreground",
    online: "bg-primary",
    offline: "bg-destructive",
  }[state];
  return (
    <span className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", dot)} aria-hidden />
      {label}
    </span>
  );
}

function FeatureCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-3">{icon}</div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
