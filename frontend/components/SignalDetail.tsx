"use client";

import type { Signal } from "@/lib/types";
import { ScoreBadge, CategoryBadge } from "./badges";
import { Button } from "@/components/ui/button";

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 break-words text-sm">{value ?? "-"}</div>
    </div>
  );
}

export function SignalDetail({
  signal,
  onClose,
}: {
  signal: Signal | null;
  onClose: () => void;
}) {
  if (!signal) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card/50 p-6 text-sm text-muted-foreground">
        Select a row to see the full record.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <ScoreBadge score={signal.signal_score} />
          <CategoryBadge category={signal.signal_category} />
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      <p className="mt-4 text-sm leading-relaxed">{signal.signal_summary}</p>

      <div className="mt-4 rounded-md border border-border bg-background p-3">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          Original record
        </div>
        {/*
          Legislation titles run long and are the whole point of the panel,
          so this scrolls rather than pushing the metadata off-screen.
        */}
        <p className="mt-1 max-h-56 overflow-y-auto text-sm leading-relaxed">
          {signal.matter_title ?? "No title provided by the source."}
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <Field label="City" value={signal.source_client} />
        <Field label="File" value={signal.matter_file} />
        <Field label="Type" value={signal.matter_type} />
        <Field label="Status" value={signal.matter_status} />
        <Field label="Body" value={signal.matter_body} />
        <Field label="Introduced" value={signal.intro_date} />
      </div>
    </div>
  );
}
