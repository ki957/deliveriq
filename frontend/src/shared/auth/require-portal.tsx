import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import type { Portal } from "@/shared/api/client";
import { useMe } from "@/shared/auth/use-me";
import { DeniedState, ErrorState, LoadingState } from "@/shared/ui/states";

// Route guard (DDR-84, DDR-99). The UI only mirrors /api/v1/me; the backend is the security boundary.
export function RequirePortal({ portal, children }: { portal: Portal; children: ReactNode }) {
  const me = useMe();
  const location = useLocation();

  if (me.isPending) return <LoadingState />;
  if (me.isError) return <ErrorState>Your account could not be loaded. Try again shortly.</ErrorState>;
  if (me.data === null) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/${portal}/login?next=${next}`} replace />;
  }
  if (!me.data.portals.includes(portal)) {
    return <DeniedState>Your account has no role for this portal.</DeniedState>;
  }
  return <>{children}</>;
}
