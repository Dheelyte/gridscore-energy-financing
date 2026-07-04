import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";

const TIER_COLOR: Record<string, string> = {
  A: "#27d08a",
  B: "#6ee7b7",
  C: "#fbbf24",
  D: "#fb923c",
  E: "#f87171",
};

export function PortfolioPage() {
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: api.portfolio });
  const p = portfolio.data;

  const pieData = p
    ? Object.entries(p.tier_distribution)
        .filter(([, n]) => n > 0)
        .map(([tier, n]) => ({ name: `Tier ${tier}`, value: n, tier }))
    : [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-4">
        <Kpi label="Customers" value={p?.total_customers ?? 0} />
        <Kpi label="Scored" value={p?.scored_customers ?? 0} />
        <Kpi label="Approval rate" value={p ? `${(p.approval_rate * 100).toFixed(0)}%` : "—"} />
        <Kpi
          label="Est. losses avoided"
          value={p ? `$${Math.round(p.estimated_losses_avoided_usd).toLocaleString()}` : "—"}
          tone="text-primary"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Risk-tier mix</CardTitle>
          <CardDescription>
            Latest score per customer · avg PD{" "}
            {p ? `${(p.average_default_probability * 100).toFixed(1)}%` : "—"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {pieData.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No scores yet — score customers in the console to populate the portfolio.
            </p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={2}
                  >
                    {pieData.map((d) => (
                      <Cell key={d.tier} fill={TIER_COLOR[d.tier] ?? "#27d08a"} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 40% 9%)",
                      border: "1px solid hsl(217 33% 18%)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
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
