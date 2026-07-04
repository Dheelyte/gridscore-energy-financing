import { ScoreGauge } from "@/components/ScoreGauge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ScoreOut } from "@/lib/api/client";

import { TopFactors } from "./TopFactors";

export function ScoreCard({ score }: { score: ScoreOut }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Energy Credit Score · pooled view</CardTitle>
        <Badge variant={score.approved ? "approve" : "reject"} className="uppercase">
          {score.approved ? "Approve" : "Reject"}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
        <div className="flex flex-col items-center gap-1">
          <ScoreGauge score={score.energy_credit_score} tier={score.risk_tier} />
          <div className="text-xs text-muted-foreground">
            Default probability{" "}
            <span className="font-medium text-foreground">
              {(score.default_probability * 100).toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="w-full flex-1">
          <div className="mb-2 text-xs font-semibold text-muted-foreground">Top factors (SHAP)</div>
          <TopFactors factors={score.top_factors} />
        </div>
      </CardContent>
    </Card>
  );
}
