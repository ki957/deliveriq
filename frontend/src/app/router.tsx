import { createBrowserRouter, Link, type RouteObject } from "react-router";

import { LoginPage } from "@/features/auth";
import { RequirePortal } from "@/shared/auth/require-portal";
import { NotBuilt } from "@/shared/ui/not-built";
import { customerConfig } from "@/portals/customer/config";
import { deliveryConfig } from "@/portals/delivery/config";
import { kitchenConfig } from "@/portals/kitchen/config";
import { managementConfig } from "@/portals/management/config";

import { Landing } from "./landing";
import type { PortalConfig } from "./portal-config";
import { PortalShell } from "./portal-shell";

export const PORTAL_CONFIGS: PortalConfig[] = [
  customerConfig,
  kitchenConfig,
  deliveryConfig,
  managementConfig,
];

function portalRoutes(config: PortalConfig): RouteObject {
  const base = `/${config.portal}`;
  const children: RouteObject[] = config.nav.map((item) => {
    const page = item.element ?? <NotBuilt title={item.label} task={item.task} />;
    const element = item.requiresLogin ? <RequirePortal portal={config.portal}>{page}</RequirePortal> : page;
    return item.to === base ? { index: true, element } : { path: item.to.slice(base.length + 1), element };
  });
  children.push({ path: "*", element: <NotFound /> });
  const shell = <PortalShell config={config} />;
  return {
    path: base,
    element: config.publicByDefault ? shell : <RequirePortal portal={config.portal}>{shell}</RequirePortal>,
    children,
  };
}

function NotFound() {
  return (
    <section className="mx-auto my-10 max-w-lg text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-text-muted">This page does not exist.</p>
      <Link to="/" className="mt-4 inline-block underline">
        Go to the start page
      </Link>
    </section>
  );
}

export const routes: RouteObject[] = [
  { path: "/", element: <Landing /> },
  { path: "/:portal/login", element: <LoginPage /> },
  ...PORTAL_CONFIGS.map(portalRoutes),
  {
    path: "*",
    element: (
      <div data-portal="none" className="min-h-screen bg-background text-text">
        <NotFound />
      </div>
    ),
  },
];

export const router = createBrowserRouter(routes);
