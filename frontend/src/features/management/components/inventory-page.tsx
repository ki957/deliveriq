import { useState } from "react";
import { Link } from "react-router";

import { useInventory, useKitchens, type Inventory } from "../api";
import { KitchenPicker, PageHeader, TableBox, Td, Th } from "./common";
import { useCan } from "@/shared/auth/require-permission";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, humanize } from "@/shared/utils/format";

/** Up to 3 decimals, trailing zeros trimmed, in the ingredient's unit (DDR-112 (9)). */
function qty(value: string | number, unit: string): string {
  return `${Number(Number(value).toFixed(3))} ${unit}`;
}

// DDR-114 (12): read-only stock, reserved, thresholds and ledger within scope; changes stay with the
// Kitchen Manager. Menu changes go through Menu Publication and Dish Availability.
export function MenuInventoryPage() {
  const kitchens = useKitchens();
  const [picked, setPicked] = useState("");
  const canPublish = useCan("menu.publish");
  const state = queryState(kitchens, { loading: "Loading kitchens…" });
  if (state) return state;
  const list = kitchens.data ?? [];
  const kitchenId = picked || list[0]?.id || "";
  return (
    <section className="mx-auto max-w-6xl space-y-4">
      <PageHeader title="Menu & Inventory">
        <p className="text-sm text-text-muted">
          Read-only. Stock is adjusted by the Kitchen Manager.{" "}
          {canPublish ? (
            <>
              Dishes are published in{" "}
              <Link to="/management/menu-publication" className="underline">
                Menu Publication
              </Link>{" "}
              and made unavailable in{" "}
              <Link to="/management/dish-availability" className="underline">
                Dish Availability
              </Link>
              .
            </>
          ) : null}
        </p>
      </PageHeader>
      {list.length === 0 ? (
        <EmptyState title="No kitchens in your scope" />
      ) : (
        <>
          <KitchenPicker kitchens={list} value={kitchenId} onChange={setPicked} />
          <KitchenInventory kitchenId={kitchenId} />
        </>
      )}
    </section>
  );
}

function KitchenInventory({ kitchenId }: { kitchenId: string }) {
  const inventory = useInventory(kitchenId);
  const state = queryState(inventory, { loading: "Loading stock…", notFound: "Kitchen not in your scope" });
  if (state) return state;
  return inventory.data ? <InventoryTables inv={inventory.data} /> : null;
}

function InventoryTables({ inv }: { inv: Inventory }) {
  return (
    <div className="space-y-6">
      <section aria-labelledby="stock" className="space-y-2">
        <h2 id="stock" className="text-lg font-semibold">
          Stock
        </h2>
        {inv.stock.some((s) => s.is_test_fixture) ? (
          <p className="text-sm">
            <TestBadge label="Test stock" /> Opening stock is test-only (DDR-37), not real quantities.
          </p>
        ) : null}
        {inv.stock.length === 0 ? (
          <p className="text-sm">No stock recorded for this kitchen.</p>
        ) : (
          <TableBox label="Stock">
            <thead className="bg-muted">
              <tr>
                <Th>Ingredient</Th>
                <Th>On hand</Th>
                <Th>Reserved</Th>
                <Th>Available</Th>
                <Th>Low-stock threshold</Th>
              </tr>
            </thead>
            <tbody>
              {inv.stock.map((s) => {
                const low =
                  s.low_stock_threshold !== null && Number(s.available) <= Number(s.low_stock_threshold);
                return (
                  <tr key={s.ingredient_id} className="border-t border-border">
                    <Td>
                      {s.name}
                      {low ? (
                        <span className="ml-2">
                          <StatusBadge tone="warning" label="Low stock" />
                        </span>
                      ) : null}
                    </Td>
                    <Td>{qty(s.on_hand, s.unit)}</Td>
                    <Td>{qty(s.reserved, s.unit)}</Td>
                    <Td>{qty(s.available, s.unit)}</Td>
                    <Td>{s.low_stock_threshold === null ? "Not set" : qty(s.low_stock_threshold, s.unit)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </TableBox>
        )}
      </section>

      <section aria-labelledby="ledger" className="space-y-2">
        <h2 id="ledger" className="text-lg font-semibold">
          Stock history (latest 100)
        </h2>
        {inv.movements.length === 0 ? (
          <p className="text-sm">No stock movements yet.</p>
        ) : (
          <TableBox label="Stock history">
            <thead className="bg-muted">
              <tr>
                <Th>When</Th>
                <Th>Ingredient</Th>
                <Th>Change</Th>
                <Th>Kind</Th>
                <Th>By role</Th>
                <Th>Reason</Th>
              </tr>
            </thead>
            <tbody>
              {inv.movements.map((m, n) => (
                <tr key={`${m.created_at}-${n}`} className="border-t border-border">
                  <Td>{formatDateTime(m.created_at)}</Td>
                  <Td>{m.ingredient_name}</Td>
                  <Td>
                    {Number(m.delta) > 0 ? "+" : ""}
                    {qty(m.delta, m.unit)}
                  </Td>
                  <Td>{humanize(m.kind)}</Td>
                  <Td>{humanize(m.actor_role)}</Td>
                  <Td>{m.reason ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </TableBox>
        )}
      </section>
    </div>
  );
}
