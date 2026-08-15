import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "./index";

/**
 * Typed versions of the plain react-redux hooks.
 *
 * Without these you'd write `useSelector((state: RootState) => ...)` at every
 * call site and lose dispatch typing. Defining them once is the standard
 * Redux Toolkit + TypeScript pattern.
 */
export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
