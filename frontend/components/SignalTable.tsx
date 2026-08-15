"use client";

import { List } from "react-window";
import type { Signal } from "@/lib/types";
import { SignalRow, type SignalRowProps } from "./SignalRow";

const ROW_HEIGHT = 68;

export function SignalTable({
  signals,
  selectedId,
  onSelect,
}: {
  signals: Signal[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  if (signals.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center text-muted-foreground">
        <p className="font-medium text-foreground">No signals match these filters</p>
        <p className="mt-1 text-sm">
          Try clearing the search box or lowering the minimum score.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex items-center gap-4 border-b border-border bg-card px-4 py-2 text-xs uppercase tracking-wide text-muted-foreground">
        <div className="w-9 shrink-0">Score</div>
        <div className="w-24 shrink-0">City / File</div>
        <div className="w-32 shrink-0">Category</div>
        <div className="min-w-0 flex-1">Why it matters</div>
      </div>

      {/*
        react-window v2 API: pass a row component plus rowProps, rather than
        v1's children-as-render-prop. Most tutorials online still show the v1
        FixedSizeList API, which will not compile against v2.

        Virtualization is overkill for ~100 rows. It exists here because the
        real dataset this models is millions of records. See README.
      */}
      <List<SignalRowProps>
        rowComponent={SignalRow}
        rowCount={signals.length}
        rowHeight={ROW_HEIGHT}
        rowProps={{ signals, selectedId, onSelect }}
        style={{ height: 560 }}
      />
    </div>
  );
}
