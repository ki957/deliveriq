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
import { RequirePermission } from "@/shared/auth/require-permission";

const gate = (permission: string, page: React.ReactNode) => (
  <RequirePermission permission={permission}>{page}</RequirePermission>
);

// #10 §13 navigation, permission-derived (MG-10). Later features (AI Copilot, AI model settings)
// stay hidden until their tasks build them (DDR-100). Task 5C adds Data & Pipelines (MG-12),
// Menu Publication and Recipe Sign-off (DDR-108).
export const managementConfig: PortalConfig = {
  portal: "management",
  title: "Management",
  publicByDefault: false,
  nav: [
    { to: "/management", label: "Overview", Icon: LayoutDashboard, task: 10, end: true },
    { to: "/management/kitchen", label: "Kitchen Operations", Icon: ChefHat, task: 10 },
    { to: "/management/delivery", label: "Delivery Operations", Icon: Truck, task: 10 },
    { to: "/management/orders", label: "Orders & Exceptions", Icon: ClipboardList, task: 10 },
    { to: "/management/menu", label: "Menu & Inventory", Icon: UtensilsCrossed, task: 10 },
    { to: "/management/customers", label: "Customers & Support", Icon: Headset, task: 10 },
    { to: "/management/payments", label: "Payments & Promotions", Icon: CreditCard, task: 10 },
    { to: "/management/reports", label: "Reports & Analytics", Icon: BarChart3, task: 13 },
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
    },
    {
      to: "/management/regional-settings",
      label: "Regional Settings",
      Icon: Settings,
      task: 10,
      permission: "management.settings.regional",
    },
    {
      to: "/management/regional-audit",
      label: "Regional Audit Logs",
      Icon: ScrollText,
      task: 10,
      permission: "management.audit.regional",
    },
    {
      to: "/management/global-staff",
      label: "Global Staff & Regional Manager Access",
      Icon: ShieldCheck,
      task: 10,
      permission: "management.regional_managers.manage",
    },
    {
      to: "/management/global-config",
      label: "Global Configuration",
      Icon: Globe,
      task: 10,
      permission: "management.settings.global",
    },
    {
      to: "/management/integrations",
      label: "Integrations & Providers",
      Icon: Plug,
      task: 10,
      permission: "management.settings.global",
    },
    {
      to: "/management/global-audit",
      label: "Global Audit Logs",
      Icon: ScrollText,
      task: 10,
      permission: "management.audit.global",
    },
    {
      to: "/management/yaml",
      label: "YAML Configuration Management",
      Icon: FileCode2,
      task: 10,
      permission: "management.settings.global",
    },
  ],
};
