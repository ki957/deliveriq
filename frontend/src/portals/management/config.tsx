import {
  BarChart3,
  ChefHat,
  ClipboardCheck,
  Database,
  Megaphone,
  ClipboardList,
  CreditCard,
  FileCode2,
  Globe,
  LayoutDashboard,
  Plug,
  ScrollText,
  Settings,
  ShieldCheck,
  Truck,
  Users,
  UtensilsCrossed,
  Headset,
  ToggleLeft,
} from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";
import { MenuPublicationPage, RecipeSignoffDetailPage, RecipeSignoffPage } from "@/features/approvals";
import { PipelinePage, PipelinesOverview, RunPage } from "@/features/data-pipelines";
import { AvailabilityDecisionsPage } from "@/features/kitchen";
import {
  AuditPage,
  DeliveryOpsPage,
  KitchenOpsPage,
  ManagementOverviewPage,
  MenuInventoryPage,
  OrderDetailPage,
  OrdersPage,
  PaymentsPage,
  StaffPage,
} from "@/features/management";
import { ReportsPage } from "@/features/reports";
import { RequirePermission } from "@/shared/auth/require-permission";
import { NotBuilt } from "@/shared/ui/not-built";

const gate = (permission: string, page: React.ReactNode) => (
  <RequirePermission permission={permission}>{page}</RequirePermission>
);
const OPS = "management.operations.view";

// #10 §13 navigation, permission-derived (MG-10). Later features (AI Copilot, AI model settings)
// stay hidden until their tasks build them (DDR-100). Task 5C adds Data & Pipelines (MG-12),
// Menu Publication and Recipe Sign-off (DDR-108). Task 10B builds the sections of DDR-114 (2); the
// others are labelled placeholders with the reason they are not built.
export const managementConfig: PortalConfig = {
  portal: "management",
  title: "Management",
  publicByDefault: false,
  nav: [
    {
      to: "/management",
      label: "Overview",
      Icon: LayoutDashboard,
      task: 10,
      end: true,
      element: gate(OPS, <ManagementOverviewPage />),
    },
    {
      to: "/management/kitchen",
      label: "Kitchen Operations",
      Icon: ChefHat,
      task: 10,
      element: gate(OPS, <KitchenOpsPage />),
    },
    {
      to: "/management/delivery",
      label: "Delivery Operations",
      Icon: Truck,
      task: 10,
      element: gate(OPS, <DeliveryOpsPage />),
    },
    {
      to: "/management/orders",
      label: "Orders & Exceptions",
      Icon: ClipboardList,
      task: 10,
      element: gate(OPS, <OrdersPage />),
      routes: [{ path: "orders/:orderId", element: gate(OPS, <OrderDetailPage />) }],
    },
    {
      to: "/management/menu",
      label: "Menu & Inventory",
      Icon: UtensilsCrossed,
      task: 10,
      permission: "management.inventory.view",
      element: gate("management.inventory.view", <MenuInventoryPage />),
    },
    {
      to: "/management/customers",
      label: "Customers & Support",
      Icon: Headset,
      task: 10,
      element: (
        <NotBuilt
          title="Customers & Support"
          reason="The sources define no support ticket or review model, so there is nothing to manage yet (DDR-114 (2))."
        />
      ),
    },
    {
      to: "/management/payments",
      label: "Payments & Promotions",
      Icon: CreditCard,
      task: 10,
      element: gate(OPS, <PaymentsPage />),
    },
    // DDR-117: ETL spec §9 KPIs over the DDR-75 marts, each "Definition pending approval (DDR-44)".
    {
      to: "/management/reports",
      label: "Reports & Analytics",
      Icon: BarChart3,
      task: 13,
      permission: "management.reports.view",
      element: gate("management.reports.view", <ReportsPage />),
    },
    {
      to: "/management/menu-publication",
      label: "Menu Publication",
      Icon: Megaphone,
      task: 5,
      permission: "menu.publish",
      element: gate("menu.publish", <MenuPublicationPage />),
    },
    // Task 8B (KI-24; DDR-111 (7)): RM own regions, CA all regions.
    {
      to: "/management/dish-availability",
      label: "Dish Availability",
      Icon: ToggleLeft,
      task: 8,
      permission: "management.unavailability.approve",
      element: gate("management.unavailability.approve", <AvailabilityDecisionsPage />),
    },
    {
      to: "/management/recipe-signoff",
      label: "Recipe Sign-off",
      Icon: ClipboardCheck,
      task: 5,
      permission: "recipes.signoff.product_owner",
      element: gate("recipes.signoff.product_owner", <RecipeSignoffPage />),
      routes: [
        {
          path: "recipe-signoff/:versionId",
          element: gate("recipes.signoff.product_owner", <RecipeSignoffDetailPage />),
        },
      ],
    },
    {
      to: "/management/data-pipelines",
      label: "Data & Pipelines",
      Icon: Database,
      task: 5,
      permission: "pipelines.view",
      element: gate("pipelines.view", <PipelinesOverview />),
      routes: [
        { path: "data-pipelines/runs/:runId", element: gate("pipelines.view", <RunPage />) },
        { path: "data-pipelines/:pipeline", element: gate("pipelines.view", <PipelinePage />) },
      ],
    },
    {
      to: "/management/staff",
      label: "Staff & Access",
      Icon: Users,
      task: 10,
      permission: "management.staff.manage",
      hideWhen: "management.regional_managers.manage",
      element: gate("management.staff.manage", <StaffPage title="Staff & Access" />),
    },
    {
      to: "/management/regional-settings",
      label: "Regional Settings",
      Icon: Settings,
      task: 10,
      permission: "management.settings.regional",
      element: (
        <NotBuilt
          title="Regional Settings"
          reason="The regional settings fields are not defined in the sources (#10 §17, DDR-114 (2)). Kitchen mode and capacity are changed in Kitchen Operations."
        />
      ),
    },
    {
      to: "/management/regional-audit",
      label: "Regional Audit Logs",
      Icon: ScrollText,
      task: 10,
      permission: "management.audit.regional",
      element: gate("management.audit.regional", <AuditPage title="Regional Audit Logs" />),
    },
    {
      to: "/management/global-staff",
      label: "Global Staff & Regional Manager Access",
      Icon: ShieldCheck,
      task: 10,
      permission: "management.regional_managers.manage",
      element: gate(
        "management.regional_managers.manage",
        <StaffPage title="Global Staff & Regional Manager Access" />,
      ),
    },
    {
      to: "/management/global-config",
      label: "Global Configuration",
      Icon: Globe,
      task: 10,
      permission: "management.settings.global",
      element: (
        <NotBuilt
          title="Global Configuration"
          reason="The global configuration fields are not defined in the sources (#10 §17, DDR-114 (2))."
        />
      ),
    },
    {
      to: "/management/integrations",
      label: "Integrations & Providers",
      Icon: Plug,
      task: 10,
      permission: "management.settings.global",
      element: (
        <NotBuilt
          title="Integrations & Providers"
          reason="No integration or provider settings are defined for management in this POC (DDR-114 (2)); AI settings come with Task 15."
        />
      ),
    },
    {
      to: "/management/global-audit",
      label: "Global Audit Logs",
      Icon: ScrollText,
      task: 10,
      permission: "management.audit.global",
      element: gate("management.audit.global", <AuditPage title="Global Audit Logs" />),
    },
    {
      to: "/management/yaml",
      label: "YAML Configuration Management",
      Icon: FileCode2,
      task: 10,
      permission: "management.settings.global",
      element: (
        <NotBuilt
          title="YAML Configuration Management"
          reason="YAML editing is blocked by an open decision (DDR-44, class B), so it is not built."
        />
      ),
    },
  ],
};
