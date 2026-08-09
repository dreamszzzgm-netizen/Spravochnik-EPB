import { useAuth } from "./auth-context";

export function useCan(permission: string): boolean {
  const { state } = useAuth();
  if (state.status !== "authenticated") return false;
  if (state.user.is_superuser) return true;
  return state.permissions.has(permission);
}
