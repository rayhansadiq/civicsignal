"use client";

import { useCallback, useEffect, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectSignal } from "@/store/filtersSlice";
import { fetchSignals, fetchStats, ApiError } from "@/lib/api";
import type { Signal, Stats } from "@/lib/types";
import { Filters } from "@/components/Filters";
import { StatsCards } from "@/components/StatsCards";
import { SignalTable } from "@/components/SignalTable";
import { SignalDetail } from "@/components/SignalDetail";

export default function Home() {
  const dispatch = useAppDispatch();
  const { q, client, category, minScore, selectedId } = useAppSelector(
    (state) => state.filters
  );

  const [signals, setSignals] = useState<Signal[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // True once a request has failed at least once and we are retrying. Drives
  // the "waking up" message: without it, a cold start is indistinguishable
  // from an outage and the page would wrongly claim to be broken.
  const [waking, setWaking] = useState(false);
  const [waitedSeconds, setWaitedSeconds] = useState(0);

  // Debounce the search box so we don't fire a request per keystroke.
  const [debouncedQ, setDebouncedQ] = useState(q);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);
      setWaking(false);
      setWaitedSeconds(0);

      const onRetry = ({ elapsedMs }: { elapsedMs: number }) => {
        if (cancelled) return;
        setWaking(true);
        setWaitedSeconds(Math.round(elapsedMs / 1000));
      };

      try {
        const [signalsRes, statsRes] = await Promise.all([
          fetchSignals(
            { q: debouncedQ, client, category, minScore },
            { onRetry, signal: controller.signal }
          ),
          fetchStats({ signal: controller.signal }),
        ]);

        // Guard against a slow earlier request resolving after a newer one
        // and overwriting fresher results.
        if (cancelled) return;

        setSignals(signalsRes.results);
        setStats(statsRes);
        setWaking(false);
      } catch (e) {
        if (cancelled || (e instanceof DOMException && e.name === "AbortError")) {
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Couldn't load signals. The API may be temporarily unavailable."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [debouncedQ, client, category, minScore]);

  const handleSelect = useCallback(
    (id: number) => dispatch(selectSignal(id)),
    [dispatch]
  );

  const selected = signals.find((s) => s.id === selectedId) ?? null;

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">
          Civic<span className="text-emerald-400">Signal</span>
        </h1>
        <p className="mt-1 text-muted-foreground">
          City and county legislation, scored into buying signals.
        </p>
      </header>

      <div className="mb-6">
        <StatsCards stats={stats} visibleCount={signals.length} />
      </div>

      <div className="mb-6">
        <Filters />
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-6 text-sm text-red-300">
          <p className="font-medium">{error}</p>
          <p className="mt-2 text-red-300/80">
            This demo runs on free-tier hosting. Try reloading in a minute.
          </p>
        </div>
      ) : loading ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          {waking ? (
            <>
              <p className="text-foreground">Waking up the API...</p>
              <p className="mt-2 text-sm text-muted-foreground">
                The backend sleeps after 15 minutes of inactivity on the free
                tier and takes about a minute to start. Waited {waitedSeconds}s.
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">Loading signals...</p>
          )}
        </div>
      ) : (
        /*
          Two columns on large screens: the list on the left, the selected
          record pinned on the right. Clicking a row previously rendered the
          detail below the table, which at most window sizes was off-screen,
          so the click looked like it did nothing.

          Below `xl` it stacks back to one column.
        */
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <SignalTable
            signals={signals}
            selectedId={selectedId}
            onSelect={handleSelect}
          />
          <aside className="xl:sticky xl:top-6 xl:self-start">
            <SignalDetail
              signal={selected}
              onClose={() => dispatch(selectSignal(null))}
            />
          </aside>
        </div>
      )}
    </main>
  );
}
