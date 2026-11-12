import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ClipboardCheck,
  History,
  Home,
  Map,
  PackageCheck,
  Truck,
  User,
} from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";

// DL-U6 screens; mobile-first with a bottom bar, not a copy of the Customer sidebar (DL-U5).
export const deliveryConfig: PortalConfig = {
  portal: "delivery",
  title: "Delivery",
  publicByDefault: false,
  nav: [
    { to: "/delivery", label: "Home", Icon: Home, task: 9, end: true },
    { to: "/delivery/assignment", label: "Assignment", Icon: ClipboardCheck, task: 9 },
    { to: "/delivery/active", label: "Active delivery", Icon: Truck, task: 9 },
    { to: "/delivery/map", label: "Map", Icon: Map, task: 9 },
    { to: "/delivery/pickup", label: "Pickup", Icon: PackageCheck, task: 9 },
    { to: "/delivery/completion", label: "Completion", Icon: CheckCircle2, task: 9 },
    { to: "/delivery/exceptions", label: "Exceptions", Icon: AlertTriangle, task: 9 },
    { to: "/delivery/notifications", label: "Notifications", Icon: Bell, task: 11 },
    { to: "/delivery/history", label: "History", Icon: History, task: 9 },
    { to: "/delivery/profile", label: "Profile", Icon: User, task: 9 },
  ],
  bottom: ["/delivery", "/delivery/history", "/delivery/notifications", "/delivery/profile"],
};
