import { Bell, Home, LifeBuoy, Settings, ShoppingCart, User, UtensilsCrossed, Receipt } from "lucide-react";

import type { PortalConfig } from "@/app/portal-config";

import { NotificationsPage } from "@/features/notifications";
import { CartPage, DishPage, MenuPage, OrderPage, OrdersPage } from "@/features/ordering";
import { RequirePortal } from "@/shared/auth/require-portal";
import { CustomerHome } from "./home";

// CU-N1 navigation. Browsing is public (CU-01); account pages need a session (CU-05).
export const customerConfig: PortalConfig = {
  portal: "customer",
  title: "Customer",
  publicByDefault: true,
  nav: [
    { to: "/customer", label: "Home", Icon: Home, end: true, element: <CustomerHome /> },
    {
      to: "/customer/menu",
      label: "Menu",
      Icon: UtensilsCrossed,
      task: 6,
      element: <MenuPage />,
      routes: [{ path: "menu/:dishId", element: <DishPage /> }],
    },
    // The cart is persisted for signed-in customers (CU-11); checkout needs a session (DDR-110 (8)).
    {
      to: "/customer/cart",
      label: "Cart",
      Icon: ShoppingCart,
      task: 6,
      requiresLogin: true,
      element: <CartPage />,
    },
    {
      to: "/customer/orders",
      label: "My Orders",
      Icon: Receipt,
      task: 6,
      requiresLogin: true,
      element: <OrdersPage />,
      routes: [
        {
          path: "orders/:orderId",
          element: (
            <RequirePortal portal="customer">
              <OrderPage />
            </RequirePortal>
          ),
        },
      ],
    },
    // CU-25, DDR-115 (10): order lifecycle in-app (no SMS, DDR-40).
    {
      to: "/customer/notifications",
      label: "Notifications",
      Icon: Bell,
      requiresLogin: true,
      element: <NotificationsPage />,
    },
    { to: "/customer/support", label: "Support", Icon: LifeBuoy, requiresLogin: true },
    { to: "/customer/profile", label: "Profile", Icon: User, requiresLogin: true },
    { to: "/customer/settings", label: "Settings", Icon: Settings, requiresLogin: true },
  ],
  bottom: ["/customer", "/customer/menu", "/customer/cart", "/customer/orders", "/customer/profile"],
};
