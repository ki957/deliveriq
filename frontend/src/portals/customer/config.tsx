import { Home, LifeBuoy, Settings, ShoppingCart, User, UtensilsCrossed, Receipt } from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";

import { CustomerHome } from "./home";

// CU-N1 navigation. Browsing is public (CU-01); account pages need a session (CU-05).
export const customerConfig: PortalConfig = {
  portal: "customer",
  title: "Customer",
  publicByDefault: true,
  nav: [
    { to: "/customer", label: "Home", Icon: Home, end: true, element: <CustomerHome /> },
    { to: "/customer/menu", label: "Menu", Icon: UtensilsCrossed, task: 6 },
    { to: "/customer/cart", label: "Cart", Icon: ShoppingCart, task: 6 },
    { to: "/customer/orders", label: "My Orders", Icon: Receipt, task: 6, requiresLogin: true },
    { to: "/customer/support", label: "Support", Icon: LifeBuoy, requiresLogin: true },
    { to: "/customer/profile", label: "Profile", Icon: User, requiresLogin: true },
    { to: "/customer/settings", label: "Settings", Icon: Settings, requiresLogin: true },
  ],
  bottom: ["/customer", "/customer/menu", "/customer/cart", "/customer/orders", "/customer/profile"],
};
