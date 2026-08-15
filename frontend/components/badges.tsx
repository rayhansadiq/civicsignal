import type { SignalCategory } from "@/lib/types";

/**
 * Score thresholds match the ones ai_signals.py was prompted with:
 *   70+  = a city is actively buying/funding something
 *   40-69 = real spending, unclear fit
 *   <40  = procedural noise
 * Keep these in sync with SYSTEM_PROMPT in backend/ai_signals.py.
 */
export function scoreTone(score: number) {
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

const SCORE_STYLES: Record<string, string> = {
  high: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  medium: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  low: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/25",
};

export function ScoreBadge({ score }: { score: number }) {
  const tone = scoreTone(score);
  return (
    <span
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-sm font-semibold tabular-nums ring-1 ring-inset ${SCORE_STYLES[tone]}`}
      title={`Signal score ${score} / 100`}
    >
      {score}
    </span>
  );
}

const CATEGORY_STYLES: Record<SignalCategory, string> = {
  renewal: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  new_initiative: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  expansion: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  low_signal: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/25",
};

const CATEGORY_LABELS: Record<SignalCategory, string> = {
  renewal: "Renewal",
  new_initiative: "New initiative",
  expansion: "Expansion",
  low_signal: "Low signal",
};

export function CategoryBadge({ category }: { category: SignalCategory }) {
  // Fall back gracefully if the model ever produces an unexpected category.
  const style = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.low_signal;
  const label = CATEGORY_LABELS[category] ?? category;

  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {label}
    </span>
  );
}
