import type { Signal, Stats } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The API was reached but returned an error status we won't retry. */
export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * The API could not be reached at all, and retrying for MAX_RETRY_MS did not
 * help. Distinct from ApiError because the two mean different things to a
 * user: "the server said no" versus "nothing answered".
 */
export class ApiUnreachableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiUnreachableError";
  }
}

/**
 * The API runs on a free tier that sleeps after 15 minutes idle and takes
 * roughly a minute to wake. A single failed fetch therefore does NOT mean
 * the service is down, and reporting it as an error is wrong: the first
 * visitor of the day would be told the site is broken while it is in fact
 * starting up.
 *
 * So we retry for up to 90 seconds, and give the caller an onRetry callback
 * so the UI can say "waking up" rather than "failed".
 */
const MAX_RETRY_MS = 90_000;
const MAX_BACKOFF_MS = 8_000;

export type FetchOptions = {
  /** Fired before each retry, so the UI can show a waking-up state. */
  onRetry?: (info: { attempt: number; elapsedMs: number }) => void;
  signal?: AbortSignal;
};

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true }
    );
  });
}

async function get<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const startedAt = Date.now();
  let attempt = 0;

  for (;;) {
    attempt += 1;
    let res: Response | null = null;

    try {
      res = await fetch(`${API_URL}${path}`, {
        cache: "no-store",
        signal: opts.signal,
      });
    } catch (e) {
      // fetch() rejects only on network-level failure: connection refused,
      // DNS, CORS block, or an aborted request. It does NOT reject on 4xx or
      // 5xx, which is why status is checked separately below.
      if (opts.signal?.aborted) throw e;
      // Otherwise fall through and retry: this is what a sleeping server
      // looks like from the browser.
    }

    if (res) {
      if (res.ok) {
        return (await res.json()) as T;
      }
      // 4xx means the request itself is wrong. Retrying will not fix a bad
      // query string, so fail fast and surface the status.
      if (res.status < 500) {
        throw new ApiError(`API returned ${res.status} for ${path}`);
      }
      // 5xx is retryable: platforms commonly return 502/503 while a service
      // is still starting.
    }

    const elapsedMs = Date.now() - startedAt;
    if (elapsedMs >= MAX_RETRY_MS) {
      throw new ApiUnreachableError(
        "The API did not respond after 90 seconds. It may be down rather than just asleep."
      );
    }

    opts.onRetry?.({ attempt, elapsedMs });

    // Exponential backoff, capped, so a long wake-up doesn't hammer the host.
    const backoff = Math.min(1000 * 2 ** (attempt - 1), MAX_BACKOFF_MS);
    await sleep(backoff, opts.signal);
  }
}

export type SignalFilters = {
  q?: string;
  client?: string;
  category?: string;
  minScore?: number;
};

export async function fetchSignals(
  filters: SignalFilters = {},
  opts: FetchOptions = {}
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

  return get(`/api/signals?${params.toString()}`, opts);
}

export async function fetchStats(opts: FetchOptions = {}): Promise<Stats> {
  return get("/api/stats", opts);
}
