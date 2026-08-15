"use client";

import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  setQuery,
  setClient,
  setCategory,
  setMinScore,
  resetFilters,
} from "@/store/filtersSlice";
import { CATEGORIES, CLIENTS } from "@/lib/types";
import { Button } from "@/components/ui/button";

const selectClass =
  "rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-emerald-500";

export function Filters() {
  const dispatch = useAppDispatch();
  const { q, client, category, minScore } = useAppSelector(
    (state) => state.filters
  );

  const isFiltered =
    q !== "" || client !== "" || category !== "" || minScore !== 0;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4">
      <input
        className={`${selectClass} min-w-[220px] flex-1`}
        placeholder="Search title or file number..."
        value={q}
        onChange={(e) => dispatch(setQuery(e.target.value))}
      />

      <select
        className={selectClass}
        value={client}
        onChange={(e) => dispatch(setClient(e.target.value))}
        aria-label="Filter by city"
      >
        <option value="">All cities</option>
        {CLIENTS.map((c) => (
          <option key={c} value={c}>
            {c[0].toUpperCase() + c.slice(1)}
          </option>
        ))}
      </select>

      <select
        className={selectClass}
        value={category}
        onChange={(e) => dispatch(setCategory(e.target.value))}
        aria-label="Filter by category"
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </select>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        Min score
        <input
          type="number"
          min={0}
          max={100}
          step={10}
          className={`${selectClass} w-20`}
          value={minScore}
          onChange={(e) => dispatch(setMinScore(Number(e.target.value) || 0))}
        />
      </label>

      {isFiltered && (
        <Button variant="outline" onClick={() => dispatch(resetFilters())}>
          Reset
        </Button>
      )}
    </div>
  );
}
