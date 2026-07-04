import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";

const tooltipStyle = {
  background: "hsl(222 40% 9%)",
  border: "1px solid hsl(217 33% 18%)",
  borderRadius: 8,
  fontSize: 12,
};

export function LenderPage() {
  const portfolio = useQuery({ queryKey: ["lenderPortfolio"], queryFn: api.lenderPortfolio });
  const network = useQuery({ queryKey: ["networkEffect"], queryFn: api.networkEffect });
  const p = portfolio.data;

  const pdData =
    p?.pd_histogram.map((b) => ({
      bucket: `${Math.round((b.from as number) * 100)}–${Math.round((b.to as number) * 100)}%`,
      count: b.count,
    })) ?? [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-4">
        <Kpi label="Scored customers" value={p?.scored_customers ?? 0} />
        <Kpi label="Approval rate" value={p ? `${(p.approval_rate * 100).toFixed(0)}%` : "—"} />
        <Kpi label="Newly bankable" value={p?.newly_bankable_customers ?? 0} tone="text-primary" />
        <Kpi
          label="Debt capacity unlocked"
          value={
            p ? `$${Math.round(p.estimated_debt_capacity_unlocked_usd).toLocaleString()}` : "—"
          }
          tone="text-primary"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cooperative network effect</CardTitle>
          <CardDescription>
            Model ROC-AUC as operators join the cooperative — <strong>retrained</strong> at each
            size (not asserted). The line rises as pooled repayment history grows.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {network.isLoading ? (
            <div className="flex h-64 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Retraining across cooperative sizes…
            </div>
          ) : (
            <div className="h-64" data-testid="network-effect-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={network.data?.points ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 18%)" />
                  <XAxis
                    dataKey="operators"
                    stroke="hsl(215 20% 65%)"
                    fontSize={12}
                    label={{
                      value: "Operators pooled",
                      position: "insideBottom",
                      offset: -4,
                      fontSize: 11,
                    }}
                  />
                  <YAxis stroke="hsl(215 20% 65%)" fontSize={12} domain={[0.6, 0.85]} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="auc"
                    stroke="#27d08a"
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    name="ROC-AUC"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Default-probability distribution</CardTitle>
            <CardDescription>
              Avg PD {p ? `${(p.average_default_probability * 100).toFixed(1)}%` : "—"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pdData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 18%)" />
                  <XAxis dataKey="bucket" stroke="hsl(215 20% 65%)" fontSize={11} />
                  <YAxis stroke="hsl(215 20% 65%)" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Operator concentration</CardTitle>
            <CardDescription>Share of cooperative customers by home operator</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {(p?.operator_concentration ?? []).map((o) => (
                <li key={String(o.operator)} className="flex items-center gap-3 text-xs">
                  <span className="w-28 shrink-0 truncate">{String(o.operator)}</span>
                  <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary/70"
                      style={{ width: `${(o.share as number) * 100}%` }}
                    />
                  </div>
                  <span className="w-12 text-right tabular-nums text-muted-foreground">
                    {((o.share as number) * 100).toFixed(0)}%
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className={`text-2xl font-bold tabular-nums ${tone ?? ""}`}>{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}
