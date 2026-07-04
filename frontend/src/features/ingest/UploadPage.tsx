import { useMutation } from "@tanstack/react-query";
import { FileUp, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api, type IngestEvent, type IngestResponse } from "@/lib/api/client";

const SAMPLE = `[
  {"raw_identifier": "+254700111222", "instalment_amount": "12.50",
   "currency": "USD", "due_date": "2024-05-05", "status": "on_time"},
  {"raw_identifier": "+254700111222", "instalment_amount": "12.50",
   "currency": "USD", "due_date": "2024-06-05", "status": "late"}
]`;

export function UploadPage() {
  const [text, setText] = useState(SAMPLE);
  const [error, setError] = useState<string | null>(null);

  const ingest = useMutation<IngestResponse, Error, IngestEvent[]>({
    mutationFn: (events) => api.ingestEvents(events, true),
  });

  const submit = () => {
    setError(null);
    let parsed: IngestEvent[];
    try {
      parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) throw new Error("Expected a JSON array of events.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid JSON");
      return;
    }
    ingest.mutate(parsed, {
      onError: (e) => setError(e instanceof ApiError ? e.message : "Upload failed"),
    });
  };

  const report = ingest.data?.report;

  return (
    <Card className="mx-auto max-w-2xl">
      <CardHeader>
        <CardTitle>Contribute repayment data</CardTitle>
        <CardDescription>
          Identifiers are anonymised at the boundary (salted hash); raw values are never stored.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          className="w-full rounded-md border border-input bg-background p-3 font-mono text-xs"
          spellCheck={false}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button onClick={submit} disabled={ingest.isPending}>
          {ingest.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileUp className="h-4 w-4" />
          )}
          Ingest events
        </Button>

        {report && (
          <div
            data-testid="ingest-report"
            className="grid grid-cols-4 gap-2 rounded-lg border border-border bg-background/40 p-3 text-center text-sm"
          >
            <Stat label="Inserted" value={report.inserted} tone="text-primary" />
            <Stat label="Duplicates" value={report.duplicates} />
            <Stat label="Failed" value={report.failed} tone="text-destructive" />
            <Stat label="Enriched" value={ingest.data?.customers_enriched ?? 0} />
          </div>
        )}
        {report?.errors?.length ? (
          <ul className="space-y-1 text-xs text-destructive">
            {report.errors.map((e) => (
              <li key={e.index}>
                Row {e.index}: {e.message}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <div className={`text-lg font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
      <div className="text-[0.7rem] text-muted-foreground">{label}</div>
    </div>
  );
}
