import { LogIn, LogOut, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";

import type { Portal } from "@/shared/api/client";
import { api } from "@/shared/api/client";
import { hasPermission, useMe, useSetMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { Wordmark } from "@/shared/ui/wordmark";
import { cn } from "@/shared/utils/cn";

import type { NavItem, PortalConfig } from "./portal-config";

const ROLE_LABELS: Record<string, string> = {
  CUSTOMER: "Customer",
  DELIVERY_AGENT: "Delivery Agent",
  KITCHEN_STAFF: "Kitchen Staff",
  KITCHEN_MANAGER: "Kitchen Manager",
  REGIONAL_MANAGER: "Regional Manager",
  CENTRAL_ADMIN: "Central Administrator",
};
const PORTAL_ROLES: Record<Portal, string[]> = {
  customer: ["CUSTOMER"],
  kitchen: ["KITCHEN_STAFF", "KITCHEN_MANAGER"],
  delivery: ["DELIVERY_AGENT"],
  management: ["REGIONAL_MANAGER", "CENTRAL_ADMIN"],
};

export function visibleNav(items: NavItem[], has: (permission: string) => boolean): NavItem[] {
  return items.filter(
    (item) => (!item.permission || has(item.permission)) && !(item.hideWhen && has(item.hideWhen)),
  );
}

function NavLinks({
  items,
  collapsed,
  onNavigate,
}: {
  items: NavItem[];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map(({ to, label, Icon, end }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={end ?? false}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 items-center gap-3 rounded-control px-3 text-sm font-medium",
                isActive ? "bg-nav-active text-nav-active-foreground" : "hover:bg-white/10",
              )
            }
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            <span className={collapsed ? "sr-only" : undefined}>{label}</span>
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

export function PortalShell({ config }: { config: PortalConfig }) {
  const me = useMe();
  const setMe = useSetMe();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const signedIn = me.data ?? null;
  const items = visibleNav(config.nav, (p) => hasPermission(signedIn, p));
  const bottomItems = items.filter((item) => config.bottom?.includes(item.to));
  const roles = (signedIn?.roles ?? [])
    .filter((g) => PORTAL_ROLES[config.portal].includes(g.role))
    .map((g) => ROLE_LABELS[g.role] ?? g.role);

  async function logout() {
    await api.POST("/api/v1/auth/logout");
    setMe(null);
    navigate(`/${config.portal}/login`);
  }

  return (
    <div data-portal={config.portal} className="flex min-h-screen flex-col bg-background text-text">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-surface focus:p-2"
      >
        Skip to content
      </a>
      <header className="on-nav flex min-h-16 items-center gap-3 border-b border-border bg-nav px-4 text-nav-foreground">
        <Button
          variant="ghost"
          className="text-nav-foreground hover:bg-white/10 lg:hidden"
          aria-label={drawerOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={drawerOpen}
          aria-controls="portal-nav-drawer"
          onClick={() => setDrawerOpen((open) => !open)}
        >
          {drawerOpen ? (
            <X className="size-5" aria-hidden="true" />
          ) : (
            <Menu className="size-5" aria-hidden="true" />
          )}
        </Button>
        <Wordmark />
        <span className="hidden text-sm font-medium sm:inline">{config.title}</span>
        <div className="ml-auto flex items-center gap-3">
          {signedIn ? (
            <>
              <span className="hidden text-right text-sm leading-tight md:block">
                <span className="block font-semibold">{signedIn.display_name}</span>
                <span className="block opacity-80" data-testid="account-roles">
                  {roles.join(", ")}
                </span>
              </span>
              <Button variant="ghost" className="text-nav-foreground hover:bg-white/10" onClick={logout}>
                <LogOut className="size-4" aria-hidden="true" />
                Sign out
              </Button>
            </>
          ) : (
            <Button asChild variant="ghost" className="text-nav-foreground hover:bg-white/10">
              <NavLink to={`/${config.portal}/login`}>
                <LogIn className="size-4" aria-hidden="true" />
                Sign in
              </NavLink>
            </Button>
          )}
        </div>
      </header>

      <div className="flex flex-1">
        <nav
          aria-label={`${config.title} navigation`}
          className={cn(
            "on-nav hidden shrink-0 bg-nav p-3 text-nav-foreground lg:block",
            collapsed ? "w-20" : "w-64",
          )}
        >
          <Button
            variant="ghost"
            className="mb-2 w-full justify-start text-nav-foreground hover:bg-white/10"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-5" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="size-5" aria-hidden="true" />
            )}
          </Button>
          <NavLinks items={items} collapsed={collapsed} />
        </nav>

        {drawerOpen ? (
          <nav
            id="portal-nav-drawer"
            aria-label={`${config.title} navigation`}
            className="on-nav fixed inset-x-0 top-16 bottom-0 z-40 overflow-y-auto bg-nav p-4 text-nav-foreground lg:hidden"
          >
            <NavLinks items={items} onNavigate={() => setDrawerOpen(false)} />
          </nav>
        ) : null}

        <main
          id="main"
          tabIndex={-1}
          className={cn("min-w-0 flex-1 p-4 md:p-6", bottomItems.length && "pb-24 lg:pb-6")}
        >
          <Outlet />
        </main>
      </div>

      {bottomItems.length ? (
        <nav
          aria-label={`${config.title} quick navigation`}
          className="on-nav fixed inset-x-0 bottom-0 z-30 border-t border-border bg-nav px-2 py-1 text-nav-foreground lg:hidden"
        >
          <ul className="flex justify-around">
            {bottomItems.map(({ to, label, Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end ?? false}
                  className={({ isActive }) =>
                    cn(
                      "flex min-h-14 min-w-16 flex-col items-center justify-center gap-0.5 rounded-control px-2 text-xs font-medium",
                      isActive && "bg-nav-active text-nav-active-foreground",
                    )
                  }
                >
                  <Icon className="size-5" aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
