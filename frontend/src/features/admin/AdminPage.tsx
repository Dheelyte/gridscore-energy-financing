import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api/client";

export function AdminPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const model = useQuery({ queryKey: ["activeModel"], queryFn: api.activeModel, retry: false });
  const h = health.data;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Operators" value={h?.operators ?? 0} />
        <Kpi label="Customers" value={h?.customers ?? 0} />
        <Kpi label="Repayment events" value={h?.repayment_events ?? 0} />
        <Kpi label="Enrichment signals" value={h?.enrichment_signals ?? 0} />
        <Kpi label="Scored" value={h?.scored_customers ?? 0} />
        <Kpi label="Consents" value={h?.active_consents ?? 0} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <OnboardOperator />
        <Card>
          <CardHeader>
            <CardTitle>Active model</CardTitle>
            <CardDescription>The deployed scoring model (from MLflow registry).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {model.isError ? (
              <p className="text-muted-foreground">No model loaded.</p>
            ) : (
              <>
                <Row label="Version" value={model.data?.version ?? "—"} />
                <Row label="ROC-AUC" value={model.data?.metrics?.roc_auc?.toFixed(3) ?? "—"} />
                <Row label="Brier" value={model.data?.metrics?.brier?.toFixed(4) ?? "—"} />
                <Row label="Threshold" value={model.data?.threshold?.toFixed(2) ?? "—"} />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <AuditSearch />
    </div>
  );
}

function OnboardOperator() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const op = await api.createOperator(name, country.toUpperCase());
      const key = await api.issueApiKey(op.id);
      return key.api_key;
    },
    onSuccess: (key) => {
      setApiKey(key);
      setName("");
      setCountry("");
      qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Onboard an operator</CardTitle>
        <CardDescription>Create a tenant and issue its machine API key.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input placeholder="Operator name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          placeholder="Country (ISO-2, e.g. KE)"
          maxLength={2}
          value={country}
          onChange={(e) => setCountry(e.target.value)}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button
          onClick={() => {
            setError(null);
            create.mutate();
          }}
          disabled={create.isPending || !name || country.length !== 2}
        >
          {create.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <KeyRound className="h-4 w-4" />
          )}
          Create + issue key
        </Button>
        {apiKey && (
          <div className="rounded-md border border-primary/40 bg-primary/10 p-2 font-mono text-xs break-all">
            {apiKey}
            <div className="mt-1 font-sans text-[0.7rem] text-muted-foreground">
              Shown once — store it securely.
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AuditSearch() {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const audit = useQuery({
    queryKey: ["audit", actor, action],
    queryFn: () => api.auditLog({ actor: actor || undefined, action: action || undefined }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit log</CardTitle>
        <CardDescription>Immutable record of every score and data access.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="actor…"
            aria-label="Filter by actor"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
          />
          <Input
            placeholder="action…"
            aria-label="Filter by action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
          <Button
            variant="outline"
            size="sm"
            aria-label="Search audit log"
            onClick={() => audit.refetch()}
          >
            <Search className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1">When</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Resource</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {(audit.data ?? []).map((r, i) => (
                <tr key={i} className="border-t border-border/60">
                  <td className="py-1 pr-2 text-muted-foreground">
                    {new Date(r.created_at).toLocaleTimeString()}
                  </td>
                  <td className="pr-2">
                    <Badge variant="muted">{r.action}</Badge>
                  </td>
                  <td className="pr-2 truncate">{r.actor}</td>
                  <td className="truncate">{r.resource}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {audit.data?.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">No audit entries.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xl font-bold tabular-nums">{value.toLocaleString()}</div>
        <div className="text-[0.7rem] text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}
