import {
  Bell,
  AlertTriangle,
  BookOpen,
  ListChecks,
  ClipboardList,
  LayoutDashboard,
  ListOrdered,
  Package,
  Settings,
} from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";
import {
  ExceptionsPage,
  InventoryPage,
  KitchenOverviewPage,
  KitchenSettingsPage,
  LiveOrdersPage,
  PreparationPage,
} from "@/features/kitchen";
import { NotificationsPage } from "@/features/notifications";
import { RecipePage, RecipesPage, ReviewQueuePage } from "@/features/recipes";
import { RequirePermission } from "@/shared/auth/require-permission";

const gate = (permission: string, page: React.ReactNode) => (
  <RequirePermission permission={permission}>{page}</RequirePermission>
);

// KI-U2 screens. Settings (mode/capacity) is Kitchen Manager only (Matrix §3.1).
export const kitchenConfig: PortalConfig = {
  portal: "kitchen",
  title: "Kitchen",
  publicByDefault: false,
  nav: [
    {
      to: "/kitchen",
      label: "Overview",
      Icon: LayoutDashboard,
      task: 8,
      end: true,
      permission: "kitchen.orders.view",
      element: gate("kitchen.orders.view", <KitchenOverviewPage />),
    },
    {
      to: "/kitchen/live-orders",
      label: "Live Orders",
      Icon: ListOrdered,
      task: 8,
      permission: "kitchen.orders.view",
      element: gate("kitchen.orders.view", <LiveOrdersPage />),
    },
    {
      to: "/kitchen/preparation",
      label: "Preparation Board",
      Icon: ClipboardList,
      task: 8,
      permission: "kitchen.orders.view",
      element: gate("kitchen.orders.view", <PreparationPage />),
    },
    {
      to: "/kitchen/recipes",
      label: "Recipes",
      Icon: BookOpen,
      task: 5,
      permission: "kitchen.recipes.view",
      element: (
        <RequirePermission permission="kitchen.recipes.view">
          <RecipesPage />
        </RequirePermission>
      ),
      routes: [
        {
          path: "recipes/:versionId",
          element: (
            <RequirePermission permission="kitchen.recipes.view">
              <RecipePage />
            </RequirePermission>
          ),
        },
      ],
    },
    {
      to: "/kitchen/review-queue",
      label: "Review Queue",
      Icon: ListChecks,
      task: 5,
      permission: "kitchen.review.view",
      element: (
        <RequirePermission permission="kitchen.review.view">
          <ReviewQueuePage />
        </RequirePermission>
      ),
    },
    {
      to: "/kitchen/inventory",
      label: "Inventory",
      Icon: Package,
      task: 8,
      permission: "kitchen.low_stock.view",
      element: gate("kitchen.low_stock.view", <InventoryPage />),
    },
    {
      to: "/kitchen/exceptions",
      label: "Exceptions",
      Icon: AlertTriangle,
      task: 8,
      permission: "kitchen.orders.view",
      element: gate("kitchen.orders.view", <ExceptionsPage />),
    },
    {
      to: "/kitchen/settings",
      label: "Settings",
      Icon: Settings,
      task: 8,
      permission: "kitchen.mode.change",
      element: gate("kitchen.mode.change", <KitchenSettingsPage />),
    },
    // KI-23, DDR-115 (10): the Kitchen Manager hears of low stock (kitchen.inventory.view is KM only).
    {
      to: "/kitchen/notifications",
      label: "Notifications",
      Icon: Bell,
      task: 11,
      permission: "kitchen.inventory.view",
      element: gate("kitchen.inventory.view", <NotificationsPage />),
    },
  ],
};
