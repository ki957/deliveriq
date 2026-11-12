import {
  AlertTriangle,
  BookOpen,
  ClipboardList,
  LayoutDashboard,
  ListOrdered,
  Package,
  Settings,
} from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";

// KI-U2 screens. Settings (mode/capacity) is Kitchen Manager only (Matrix §3.1).
export const kitchenConfig: PortalConfig = {
  portal: "kitchen",
  title: "Kitchen",
  publicByDefault: false,
  nav: [
    { to: "/kitchen", label: "Overview", Icon: LayoutDashboard, task: 8, end: true },
    { to: "/kitchen/live-orders", label: "Live Orders", Icon: ListOrdered, task: 8 },
    { to: "/kitchen/preparation", label: "Preparation Board", Icon: ClipboardList, task: 8 },
    { to: "/kitchen/recipes", label: "Recipes", Icon: BookOpen, task: 5 },
    { to: "/kitchen/inventory", label: "Inventory", Icon: Package, task: 8 },
    { to: "/kitchen/exceptions", label: "Exceptions", Icon: AlertTriangle, task: 8 },
    {
      to: "/kitchen/settings",
      label: "Settings",
      Icon: Settings,
      task: 8,
      permission: "kitchen.mode.change",
    },
  ],
};
