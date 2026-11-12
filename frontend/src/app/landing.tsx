import { ChefHat, LayoutDashboard, ShoppingBag, Truck } from "lucide-react";
import { Link } from "react-router";

import { Wordmark } from "@/shared/ui/wordmark";

const PORTALS = [
  { to: "/customer", title: "Customer", text: "Browse and order food", Icon: ShoppingBag },
  { to: "/kitchen", title: "Kitchen", text: "Kitchen staff and managers", Icon: ChefHat },
  { to: "/delivery", title: "Delivery", text: "Delivery agents", Icon: Truck },
  {
    to: "/management",
    title: "Management",
    text: "Regional managers and administrators",
    Icon: LayoutDashboard,
  },
];

// The URL decides the portal (DDR-99); this page only links to them.
export function Landing() {
  return (
    <div data-portal="none" className="min-h-screen bg-background p-6 text-text">
      <main className="mx-auto max-w-3xl">
        <Wordmark />
        <h1 className="mt-6 text-2xl font-semibold">Choose a portal</h1>
        <p className="mt-1 text-text-muted">Portfolio demo of a single cloud kitchen in Chennai.</p>
        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {PORTALS.map(({ to, title, text, Icon }) => (
            <li key={to}>
              <Link
                to={to}
                className="flex min-h-20 items-center gap-4 rounded-panel border border-border bg-surface p-4 hover:bg-muted"
              >
                <Icon className="size-7 shrink-0" aria-hidden="true" />
                <span>
                  <span className="block font-semibold">{title}</span>
                  <span className="block text-sm text-text-muted">{text}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
