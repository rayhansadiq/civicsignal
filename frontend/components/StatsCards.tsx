import type { Stats } from "@/lib/types";

function Card({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-1 text-2xl font-semibold tabular-nums ${
          accent ? "text-emerald-400" : ""
        }`}
      >
        {value}
      </div>
      {hint && (
        <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
      )}
    </div>
  );
}

export function StatsCards({
  stats,
  visibleCount,
}: {
  stats: Stats | null;
  visibleCount: number;
}) {
  const noise =
    stats && stats.total_scored > 0
      ? Math.round(
          ((stats.total_scored - stats.high_signal_count) /
            stats.total_scored) *
            100
        )
      : null;

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card
        label="Records scored"
        value={stats?.total_scored ?? "-"}
        hint="Seattle + Oakland"
      />
      <Card
        label="High signal (70+)"
        value={stats?.high_signal_count ?? "-"}
        hint="Worth a salesperson's time"
        accent
      />
      <Card
        label="Noise filtered"
        value={noise === null ? "-" : `${noise}%`}
        hint="Why the scoring layer exists"
      />
      <Card
        label="Matching filters"
        value={visibleCount}
        hint="Currently shown"
      />
    </div>
  );
}
