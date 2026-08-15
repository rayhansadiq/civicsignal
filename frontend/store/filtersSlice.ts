import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type FiltersState = {
  q: string;
  client: string; // "" = all cities
  category: string; // "" = all categories
  minScore: number; // 0 = no minimum
  selectedId: number | null;
};

const initialState: FiltersState = {
  q: "",
  client: "",
  category: "",
  minScore: 0,
  selectedId: null,
};

/**
 * Redux holds only filter and selection state, deliberately not the fetched
 * signals themselves. Caching server data in Redux is a common overreach
 * that means writing your own invalidation logic; the signals live in
 * component state and are refetched when filters change.
 */
const filtersSlice = createSlice({
  name: "filters",
  initialState,
  reducers: {
    setQuery(state, action: PayloadAction<string>) {
      state.q = action.payload;
    },
    setClient(state, action: PayloadAction<string>) {
      state.client = action.payload;
    },
    setCategory(state, action: PayloadAction<string>) {
      state.category = action.payload;
    },
    setMinScore(state, action: PayloadAction<number>) {
      // Clamp so a stray input can't send min_score=9999 and silently
      // return an empty list that looks like a bug.
      state.minScore = Math.max(0, Math.min(100, action.payload));
    },
    selectSignal(state, action: PayloadAction<number | null>) {
      state.selectedId = action.payload;
    },
    resetFilters() {
      return initialState;
    },
  },
});

export const {
  setQuery,
  setClient,
  setCategory,
  setMinScore,
  selectSignal,
  resetFilters,
} = filtersSlice.actions;

export default filtersSlice.reducer;
