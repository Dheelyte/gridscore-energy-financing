import { ArrowRight, Network, Sparkles } from "lucide-react";
import { useState } from "react";

import { ScoreGauge } from "@/components/ScoreGauge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { CooperativeOut, ScoreOut } from "@/lib/api/client";
import { cn } from "@/lib/utils";

function DecisionBadge({ approved }: { approved: boolean }) {
  return (
    <Badge variant={approved ? "approve" : "reject"} className="text-[0.7rem] uppercase">
      {approved ? "Approve" : "Reject"}
    </Badge>
  );
}

function ScoreColumn({
  title,
  subtitle,
  score,
}: {
  title: string;
  subtitle: string;
  score: ScoreOut;
}) {
  return (
    <div className="flex flex-1 flex-col items-center gap-2 rounded-lg border border-border bg-background/40 p-4">
      <div className="text-center">
        <div className="text-sm font-semibold">{title}</div>
        <div className="text-xs text-muted-foreground">{subtitle}</div>
      </div>
      <ScoreGauge score={score.energy_credit_score} tier={score.risk_tier} size={190} />
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>PD {(score.default_probability * 100).toFixed(1)}%</span>
        <DecisionBadge approved={score.approved} />
      </div>
    </div>
  );
}

/** The cooperative network effect, on screen: the solo (home-operator-only)
 *  view versus the pooled cooperative view, revealed with an animation, plus the
 *  reject → approve decision flip. */
export function CooperativePanel({ data }: { data: CooperativeOut }) {
  const [revealed, setRevealed] = useState(false);

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Cooperative network effect</span>
          </div>
          {!revealed && (
            <Button size="sm" onClick={() => setRevealed(true)}>
              <Sparkles className="h-4 w-4" /> Pool the cooperative
            </Button>
          )}
        </div>

        <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center">
          <ScoreColumn
            title="Solo view"
            subtitle="Home operator's history only"
            score={data.solo}
          />

          <div className="flex shrink-0 flex-col items-center gap-1 px-2">
            <ArrowRight
              className={cn(
                "h-6 w-6 text-primary transition-transform duration-700",
                revealed ? "translate-x-0 opacity-100" : "opacity-40",
              )}
            />
            <span className="text-[0.7rem] text-muted-foreground">+{data.score_delta} pts</span>
          </div>

          <div
            className={cn(
              "flex-1 transition-all duration-700",
              revealed
                ? "translate-y-0 opacity-100"
                : "pointer-events-none translate-y-2 opacity-0",
            )}
            data-testid="pooled-column"
          >
            <ScoreColumn
              title="Pooled view"
              subtitle="Full cooperative history"
              score={data.pooled}
            />
          </div>
        </div>

        {revealed && (
          <div
            data-testid="lift-summary"
            className="grid grid-cols-3 gap-3 rounded-lg border border-border bg-background/40 p-3 text-center"
          >
            <Metric label="PD reduction" value={`${(data.pd_delta * 100).toFixed(1)} pts`} />
            <Metric label="Score lift" value={`+${data.score_delta}`} />
            <Metric label="Confidence ↑" value={data.confidence_delta.toFixed(2)} />
          </div>
        )}

        {revealed && data.decision_flips && (
          <div
            data-testid="decision-flip"
            className="animate-in rounded-lg border border-primary/40 bg-primary/10 p-3 text-center text-sm font-semibold text-primary"
          >
            Decision flips: <span className="text-destructive">Reject</span>{" "}
            <ArrowRight className="inline h-4 w-4" /> <span className="text-primary">Approve</span>{" "}
            — unlocked by the cooperative.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm font-semibold tabular-nums">{value}</div>
      <div className="text-[0.7rem] text-muted-foreground">{label}</div>
    </div>
  );
}
