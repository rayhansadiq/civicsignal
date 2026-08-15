import type { Signal, Stats } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Thrown when the backend is unreachable or returns a non-2xx status.
 * The UI catches this to show a "is the backend running?" message rather
 * than rendering a blank page, which is what you'd otherwise see, and it
 * looks identical to a bug in the frontend.
 */
export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string): Promise<T> {
  let res: Response;

  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  } catch {
    // fetch() only rejects on network-level failures (server down, DNS,
    // CORS block), not on 4xx/5xx, which is why the status check is separate.
    throw new ApiError(
      "Can't reach the CivicSignal API. Is the backend running on port 8000?"
    );
  }

  if (!res.ok) {
    throw new ApiError(`API returned ${res.status} for ${path}`);
  }

  return res.json() as Promise<T>;
}

export type SignalFilters = {
  q?: string;
  client?: string;
  category?: string;
  minScore?: number;
};

export async function fetchSignals(
  filters: SignalFilters = {}
): Promise<{ count: number; results: Signal[] }> {
  const params = new URLSearchParams();

  if (filters.q) params.set("q", filters.q);
  if (filters.client) params.set("client", filters.client);
  if (filters.category) params.set("category", filters.category);
  if (filters.minScore) params.set("min_score", String(filters.minScore));

  // Always pass limit explicitly. The API defaults to 100 and there are
  // currently exactly 100 records, so omitting it happens to return
  // everything today, and would silently truncate the moment another
  // city is ingested. 200 is the API's maximum.
  params.set("limit", "200");

  return get(`/api/signals?${params.toString()}`);
}

export async function fetchStats(): Promise<Stats> {
  return get("/api/stats");
}
