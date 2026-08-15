import { configureStore } from "@reduxjs/toolkit";
import filtersReducer from "./filtersSlice";

export const makeStore = () =>
  configureStore({
    reducer: {
      filters: filtersReducer,
    },
  });

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
