/**
 * Shape of a scored public-sector record, as returned by the CivicSignal API.
 *
 * Most fields are nullable because Legistar records are inconsistent: a
 * matter might have no title, no committee body, or no dates. The AI-derived
 * fields (signal_*) are always present, because ai_signals.py validates and
 * defaults them before writing to the database.
 */
export type Signal = {
  id: number;
  source_client: string;
  matter_file: string | null;
  matter_name: string | null;
  matter_title: string | null;
  matter_type: string | null;
  matter_status: string | null;
  matter_body: string | null;
  intro_date: string | null;
  agenda_date: string | null;
  signal_score: number;
  signal_category: SignalCategory;
  signal_summary: string;
};

export type SignalCategory =
  | "renewal"
  | "new_initiative"
  | "expansion"
  | "low_signal";

export type Stats = {
  total_scored: number;
  high_signal_count: number;
};

export const CATEGORIES: { value: SignalCategory; label: string }[] = [
  { value: "renewal", label: "Renewal" },
  { value: "new_initiative", label: "New initiative" },
  { value: "expansion", label: "Expansion" },
  { value: "low_signal", label: "Low signal" },
];

/**
 * Fallback city list. The API now exposes GET /api/clients; wiring the
 * filter to that endpoint instead of this constant is a pending cleanup.
 */
export const CLIENTS = ["seattle", "oakland"];
