"use client";

import type { RowComponentProps } from "react-window";
import type { Signal } from "@/lib/types";
import { ScoreBadge, CategoryBadge } from "./badges";

/**
 * Props passed through react-window's `rowProps`. The library injects
 * `index`, `style`, and `ariaAttributes` on top of these.
 */
export type SignalRowProps = {
  signals: Signal[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

export function SignalRow({
  index,
  style,
  ariaAttributes,
  signals,
  selectedId,
  onSelect,
}: RowComponentProps<SignalRowProps>) {
  const signal = signals[index];
  if (!signal) return null;

  const isSelected = signal.id === selectedId;

  return (
    <div
      style={style}
      {...ariaAttributes}
      onClick={() => onSelect(signal.id)}
      className={`flex cursor-pointer items-center gap-4 border-b border-border px-4 transition-colors hover:bg-accent/40 ${
        isSelected ? "bg-accent/60" : ""
      }`}
    >
      <ScoreBadge score={signal.signal_score} />

      <div className="w-24 shrink-0 text-sm">
        <div className="capitalize">{signal.source_client}</div>
        <div className="truncate text-xs text-muted-foreground">
          {signal.matter_file ?? "-"}
        </div>
      </div>

      <div className="w-32 shrink-0">
        <CategoryBadge category={signal.signal_category} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-sm">{signal.signal_summary}</div>
        <div className="truncate text-xs text-muted-foreground">
          {signal.matter_title ?? "No title"}
        </div>
      </div>
    </div>
  );
}
