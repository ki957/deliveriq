import { lazy, Suspense, type ReactNode } from "react";
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
import {
  ActiveDeliveryPage,
  AssignmentPage,
  CompletionPage,
  DeliveryExceptionsPage,
  DeliveryHistoryPage,
  DeliveryHomePage,
  DeliveryProfilePage,
  PickupPage,
} from "@/features/delivery";
import { RequirePermission } from "@/shared/auth/require-permission";
import { LoadingState } from "@/shared/ui/states";

// Leaflet loads only when the map is opened (keeps the other portals light).
const DeliveryMapPage = lazy(() => import("@/features/delivery/components/map-page"));

const gate = (page: ReactNode) => (
  <RequirePermission permission="delivery.assignments.view">{page}</RequirePermission>
);

// DL-U6 screens; mobile-first with a bottom bar, not a copy of the Customer sidebar (DL-U5).
export const deliveryConfig: PortalConfig = {
  portal: "delivery",
  title: "Delivery",
  publicByDefault: false,
  nav: [
    { to: "/delivery", label: "Home", Icon: Home, task: 9, end: true, element: gate(<DeliveryHomePage />) },
    {
      to: "/delivery/assignment",
      label: "Assignment",
      Icon: ClipboardCheck,
      task: 9,
      element: gate(<AssignmentPage />),
    },
    {
      to: "/delivery/active",
      label: "Active delivery",
      Icon: Truck,
      task: 9,
      element: gate(<ActiveDeliveryPage />),
    },
    {
      to: "/delivery/map",
      label: "Map",
      Icon: Map,
      task: 9,
      element: gate(
        <Suspense fallback={<LoadingState label="Loading the map…" />}>
          <DeliveryMapPage />
        </Suspense>,
      ),
    },
    { to: "/delivery/pickup", label: "Pickup", Icon: PackageCheck, task: 9, element: gate(<PickupPage />) },
    {
      to: "/delivery/completion",
      label: "Completion",
      Icon: CheckCircle2,
      task: 9,
      element: gate(<CompletionPage />),
    },
    {
      to: "/delivery/exceptions",
      label: "Exceptions",
      Icon: AlertTriangle,
      task: 9,
      element: gate(<DeliveryExceptionsPage />),
    },
    { to: "/delivery/notifications", label: "Notifications", Icon: Bell, task: 11 },
    {
      to: "/delivery/history",
      label: "History",
      Icon: History,
      task: 9,
      element: gate(<DeliveryHistoryPage />),
    },
    {
      to: "/delivery/profile",
      label: "Profile",
      Icon: User,
      task: 9,
      element: gate(<DeliveryProfilePage />),
    },
  ],
  bottom: ["/delivery", "/delivery/active", "/delivery/completion", "/delivery/history", "/delivery/profile"],
};
