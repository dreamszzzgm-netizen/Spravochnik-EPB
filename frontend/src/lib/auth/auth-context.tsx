"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api/errors";
import { getCurrentUser, logout as apiLogout } from "@/lib/api/resources";
import type { CurrentUserResponse } from "@/lib/api/types";

export type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: CurrentUserResponse; permissions: Set<string> }
  | { status: "unauthenticated" }
  | { status: "forbidden" }
  | { status: "offline" };

interface AuthContextValue {
  state: AuthState;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ status: "loading" });
    try {
      const user = await getCurrentUser({ signal: controller.signal });
      if (controller.signal.aborted) return;
      setState({
        status: "authenticated",
        user,
        permissions: new Set(user.permissions ?? []),
      });
    } catch (error: unknown) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError) {
        setState(error.status === 401 ? { status: "unauthenticated" } : error.status === 403 ? { status: "forbidden" } : { status: "offline" });
      } else {
        setState({ status: "offline" });
      }
    }
  }, []);

  const logout = useCallback(async () => {
    try { await apiLogout(); } catch { /* already logged out */ }
    setState({ status: "unauthenticated" });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;

    async function load() {
      controller = new AbortController();
      abortRef.current = controller;
      setState({ status: "loading" });
      try {
        const user = await getCurrentUser({ signal: controller.signal });
        if (cancelled) return;
        setState({
          status: "authenticated",
          user,
          permissions: new Set(user.permissions ?? []),
        });
      } catch (error: unknown) {
        if (cancelled) return;
        if (error instanceof ApiError) {
          setState(error.status === 401 ? { status: "unauthenticated" } : error.status === 403 ? { status: "forbidden" } : { status: "offline" });
        } else {
          setState({ status: "offline" });
        }
      }
    }

    queueMicrotask(() => { void load(); });
    return () => {
      cancelled = true;
      controller?.abort();
    };
  }, []);

  const value = useMemo(() => ({ state, refresh, logout }), [state, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
