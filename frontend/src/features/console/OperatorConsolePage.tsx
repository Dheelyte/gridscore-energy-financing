import { useQuery } from "@tanstack/react-query";
import { Search, Sparkles, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CooperativePanel } from "@/features/scoring/CooperativePanel";
import { ScoreCard } from "@/features/scoring/ScoreCard";
import { api } from "@/lib/api/client";
import { demoIdentityHash } from "@/lib/demo";
import { cn } from "@/lib/utils";

export function OperatorConsolePage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const customers = useQuery({ queryKey: ["customers"], queryFn: api.listCustomers });

  const filtered = useMemo(() => {
    const list = customers.data ?? [];
    const q = query.trim().toLowerCase();
    return (q ? list.filter((c) => c.identity_hash.includes(q)) : list).slice(0, 40);
  }, [customers.data, query]);

  const selectDemo = async () => {
    const hash = await demoIdentityHash();
    const match = (customers.data ?? []).find((c) => c.identity_hash === hash);
    if (match) setSelected(match.id);
  };

  const score = useQuery({
    queryKey: ["score", selected],
    queryFn: () => api.score(selected!, "pooled"),
    enabled: !!selected,
  });
  const cooperative = useQuery({
    queryKey: ["cooperative", selected],
    queryFn: () => api.scoreCooperative(selected!),
    enabled: !!selected,
  });

  useEffect(() => {
    if (!selected && filtered.length > 0) setSelected(filtered[0].id);
  }, [filtered, selected]);

  return (
    <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Customers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by identity hash…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={selectDemo}>
            <Sparkles className="h-4 w-4" /> Borderline demo customer
          </Button>
          <ul className="max-h-[420px] space-y-1 overflow-y-auto">
            {customers.isLoading && (
              <li className="flex items-center gap-2 p-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" /> Loading…
              </li>
            )}
            {filtered.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => setSelected(c.id)}
                  className={cn(
                    "w-full truncate rounded-md px-2 py-1.5 text-left font-mono text-xs",
                    selected === c.id ? "bg-secondary text-foreground" : "hover:bg-secondary/60",
                  )}
                >
                  {c.identity_hash.slice(0, 18)}…
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="space-y-5">
        {!selected && (
          <Card>
            <CardContent className="p-10 text-center text-sm text-muted-foreground">
              Select a customer to score.
            </CardContent>
          </Card>
        )}
        {(score.isLoading || cooperative.isLoading) && selected && (
          <Card>
            <CardContent className="flex items-center gap-2 p-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Scoring…
            </CardContent>
          </Card>
        )}
        {score.data && <ScoreCard score={score.data} />}
        {cooperative.data && <CooperativePanel data={cooperative.data} />}
      </div>
    </div>
  );
}
