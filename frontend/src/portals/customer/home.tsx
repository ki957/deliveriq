import { Link } from "react-router";

import { useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";

export function CustomerHome() {
  const me = useMe();
  const name = me.data?.display_name;
  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold">{name ? `Welcome, ${name}` : "Welcome to DeliverIQ"}</h1>
      <p className="mt-2 text-text-muted">
        One cloud kitchen in Chennai. Choose your location to see what we can deliver to you.
      </p>
      <Button asChild className="mt-4">
        <Link to="/customer/menu">Browse the menu</Link>
      </Button>
      {me.data === null ? (
        <div className="mt-6 rounded-panel border border-border bg-muted p-4">
          <p className="font-medium">Sign in with your mobile number to order.</p>
          <Button asChild className="mt-3">
            <Link to="/customer/login">Sign in</Link>
          </Button>
        </div>
      ) : null}
    </section>
  );
}
