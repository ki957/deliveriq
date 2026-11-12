import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { Portal } from "@/shared/api/client";

export interface NavItem {
  to: string;
  label: string;
  Icon: LucideIcon;
  /** Show only when /api/v1/me grants this permission (MG-10: permission-derived navigation). */
  permission?: string;
  /** Hide when this permission is held (e.g. CA sees the global staff screen instead). */
  hideWhen?: string;
  /** Plan task that builds the screen; undefined when the plan names no task. */
  task?: number;
  /** Customer pages that need a session; staff portals always do. */
  requiresLogin?: boolean;
  end?: boolean;
  /** Custom page instead of the "Not built yet" placeholder. */
  element?: ReactNode;
}

export interface PortalConfig {
  portal: Portal;
  title: string;
  /** Staff portals need a session for every page; the customer portal is browsable (CU-01). */
  publicByDefault: boolean;
  nav: NavItem[];
  /** Paths shown in the mobile bottom bar (Customer CU-U3, Delivery DL-U1). */
  bottom?: string[];
}
