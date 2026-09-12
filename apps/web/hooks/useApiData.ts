"use client";

/**
 * Load-on-mount data fetching for the authenticated screens.
 *
 * Why client-side fetching at all: the access token lives in browser
 * localStorage (the documented MVP strategy, lib/auth/storage), which
 * server components cannot read — a server-side fetch can never attach
 * the `Authorization` header, so every business endpoint would answer
 * 401. The screens therefore fetch in the browser, where the token is,
 * after the AuthGate has confirmed the session. The httpOnly-cookie /
 * BFF migration (docs/06 §4h) remains the documented future option.
 *
 * The hook owns the three states every screen needs — loading, error,
 * success — with cancellation on unmount (no state writes after the
 * screen is gone) and non-ApiError failures normalized to the same
 * classification the rest of the UI branches on.
 *
 * The fetcher is read through a ref and the effect runs once per
 * mount: these screens load their data on entry, not reactively.
 * Resource-keyed screens (e.g. event detail) remount via a React
 * `key` from their page when the id in the URL changes.
 */

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

export type ApiDataState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

export function useApiData<T>(fetcher: () => Promise<T>): ApiDataState<T> {
  const fetcherRef = useRef(fetcher);
  const [state, setState] = useState<ApiDataState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            cause instanceof ApiError
              ? cause
              : new ApiError("server", String(cause)),
        });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
