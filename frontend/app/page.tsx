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

  // Debounce the search box so we don't fire a request per keystroke.
  const [debouncedQ, setDebouncedQ] = useState(q);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [signalsRes, statsRes] = await Promise.all([
          fetchSignals({ q: debouncedQ, client, category, minScore }),
          fetchStats(),
        ]);

        // Guard against a slow earlier request resolving after a newer one
        // and overwriting fresher results.
        if (cancelled) return;

        setSignals(signalsRes.results);
        setStats(statsRes);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Something went wrong loading signals."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
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
            Start it with{" "}
            <code className="rounded bg-red-950 px-1.5 py-0.5">
              uvicorn main:app --reload --port 8000
            </code>{" "}
            from the <code>backend/</code> folder, with the venv active.
          </p>
        </div>
      ) : loading ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center text-muted-foreground">
          Loading signals…
        </div>
      ) : (
        /*
          Two columns on large screens: the list on the left, the selected
          record pinned on the right. Clicking a row previously rendered the
          detail below the table, which at most window sizes was off-screen,
          so the click looked like it did nothing.

          Below `xl` it stacks back to one column, where the detail sits under
          the table and `scroll-mt` keeps it clear of the viewport edge.
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
