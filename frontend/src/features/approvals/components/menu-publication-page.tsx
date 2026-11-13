import { useState } from "react";

import { MENU_ACTIONS, useManagedMenu, useMenuTransition, type MenuItem } from "../api";
import { actionError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { menuStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatPaise } from "@/shared/utils/format";

// Menu publication (DDR-11, DDR-31): CA any region, RM assigned regions; the list is already scoped
// by the backend. Readiness and the ACTIVE-recipe rule are enforced in the database.
export function MenuPublicationPage() {
  const menu = useManagedMenu();
  const state = queryState(menu, { loading: "Loading menu items…" });
  if (state) return state;
  const items = menu.data ?? [];

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Menu publication</h1>
      <p className="mt-1 text-sm text-text-muted">
        An item can be published only with an active recipe version and every readiness field. Only TEST
        dishes are published in this POC (DDR-50).
      </p>
      {items.length === 0 ? (
        <EmptyState title="No menu items in your regions" />
      ) : (
        <ul className="mt-4 divide-y divide-border rounded-panel border border-border bg-surface">
          {items.map((item) => (
            <MenuRow key={item.id} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

function MenuRow({ item }: { item: MenuItem }) {
  const transition = useMenuTransition();
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const actions = MENU_ACTIONS.filter((a) => a.from === item.publication_status);
  const [tone, label] = menuStatus(item.publication_status);

  return (
    <li className="p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="flex flex-wrap items-center gap-2 font-medium">
            <span data-testid="menu-item-name">{item.name}</span>
            {item.is_test_fixture ? <TestBadge /> : null}
          </p>
          <p className="text-text-muted">
            {formatPaise(item.price_paise)} · {item.category ?? "No category"} · recipe{" "}
            {item.has_active_recipe ? "active" : "not active"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={tone} label={label} />
          {actions.map((a) => (
            <Button
              key={a.action}
              variant={a.action === "publish" ? "primary" : "secondary"}
              disabled={transition.isPending}
              onClick={async () => {
                setMessage(null);
                try {
                  await transition.mutateAsync({ id: item.id, action: a.action });
                  setMessage({ text: `${a.label}: done.`, error: false });
                } catch (e) {
                  setMessage({ text: actionError(e), error: true });
                }
              }}
            >
              {a.label}
            </Button>
          ))}
        </div>
      </div>
      {message ? (
        <p role={message.error ? "alert" : "status"} className="mt-2">
          {message.text}
        </p>
      ) : null}
    </li>
  );
}
