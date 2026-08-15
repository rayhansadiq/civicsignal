"use client";

import { useRef, type ReactNode } from "react";
import { Provider } from "react-redux";
import { makeStore, type AppStore } from "@/store";

/**
 * Redux Provider, isolated into its own client component.
 *
 * app/layout.tsx stays a server component (the Next.js default). Only this
 * subtree is client-side, which is the standard App Router pattern;
 * marking the whole layout "use client" would opt the entire app out of
 * server rendering.
 *
 * The store is created inside a ref rather than at module scope so each
 * request gets its own store on the server. A module-level store would be
 * shared across users in a server environment.
 */
export function Providers({ children }: { children: ReactNode }) {
  const storeRef = useRef<AppStore | null>(null);

  if (storeRef.current === null) {
    storeRef.current = makeStore();
  }

  return <Provider store={storeRef.current}>{children}</Provider>;
}
