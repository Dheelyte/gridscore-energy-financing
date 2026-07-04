import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface Factor {
  feature: string;
  label: string;
  value: number;
  contribution: number;
  direction: string;
}

/** SHAP "top factors": horizontal bars sized by |contribution|, coloured by
 *  whether the factor increases (red) or decreases (green) default risk. */
export function TopFactors({ factors }: { factors: Factor[] }) {
  const max = Math.max(...factors.map((f) => Math.abs(f.contribution)), 0.0001);
  return (
    <ul className="flex flex-col gap-2.5">
      {factors.map((f) => {
        const increases = f.direction === "increases";
        const width = `${Math.max((Math.abs(f.contribution) / max) * 100, 6)}%`;
        return (
          <li key={f.feature} className="flex items-center gap-3">
            <div className="w-44 shrink-0 text-xs text-foreground/90">{f.label}</div>
            <div className="relative h-3 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "absolute inset-y-0 left-0 rounded-full transition-[width] duration-700",
                  increases ? "bg-destructive/80" : "bg-primary/80",
                )}
                style={{ width }}
              />
            </div>
            <div
              className={cn(
                "flex w-16 shrink-0 items-center justify-end gap-1 text-xs",
                increases ? "text-destructive" : "text-primary",
              )}
            >
              {increases ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : (
                <ArrowDownRight className="h-3 w-3" />
              )}
              {f.contribution.toFixed(2)}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
