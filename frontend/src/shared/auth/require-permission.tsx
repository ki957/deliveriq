import type { ReactNode } from "react";

import { hasPermission, useMe } from "./use-me";
import { DeniedState, LoadingState } from "@/shared/ui/states";

// Page-level guard: a direct URL to a screen the account cannot use shows the denied state.
// UI only; the backend refuses the same calls (DDR-99).
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <LoadingState />;
  if (!hasPermission(me.data, permission)) return <DeniedState />;
  return <>{children}</>;
}

export function useCan(permission: string): boolean {
  return hasPermission(useMe().data, permission);
}
