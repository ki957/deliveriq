import { useState } from "react";

import {
  useAdjustStock,
  useAvailabilityRequests,
  useKitchenDishes,
  useKitchenQueue,
  useLowStock,
  useRequestAvailability,
  useSetThreshold,
  useStock,
  type AvailabilityKind,
  type Stock,
} from "../api";
import { formatQty, refusalText } from "../format";
import { AvailabilityList } from "./availability-list";
import { hasPermission, useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";

// KI-21–KI-24, DDR-111 (9), DDR-112 (6): KM sees full stock; Kitchen Staff see low-stock alerts only.
export function InventoryPage() {
  const me = useMe();
  const full = hasPermission(me.data, "kitchen.inventory.view");
  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Inventory</h1>
      <p className="text-sm text-text-muted">
        Opening stock is test-only (DDR-37) and is labelled "Test stock". It is not real kitchen stock.
      </p>
      {full ? <StockTable /> : <LowStockList />}
      <DishAvailability />
    </section>
  );
}

function StockTable() {
  const stock = useStock(true);
  const state = queryState(stock, { loading: "Loading stock…" });
  if (state) return state;
  const rows = stock.data ?? [];
  if (rows.length === 0) return <EmptyState title="No stock records" />;
  return (
    <section aria-labelledby="stock">
      <h2 id="stock" className="text-xl font-semibold">
        Stock
      </h2>
      <ul className="mt-3 grid gap-3 xl:grid-cols-2" aria-label="Ingredient stock">
        {rows.map((s) => (
          <StockRow key={s.ingredient_id} stock={s} />
        ))}
      </ul>
    </section>
  );
}

function StockRow({ stock: s }: { stock: Stock }) {
  const [editing, setEditing] = useState<"adjust" | "threshold" | null>(null);
  return (
    <li className="rounded-panel border border-border bg-surface p-4 text-sm" data-testid="stock-row">
      <p className="flex flex-wrap items-center gap-2 text-base font-semibold">
        {s.name}
        {s.is_test_fixture ? <TestBadge label="Test stock" /> : null}
        {s.is_low ? <StatusBadge tone="danger" label="Low stock" /> : null}
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
        <Fact term="On hand" value={formatQty(s.on_hand, s.unit)} />
        <Fact term="Reserved" value={formatQty(s.reserved, s.unit)} />
        <Fact term="Available" value={formatQty(s.available, s.unit)} />
        <Fact
          term="Threshold"
          value={s.low_stock_threshold === null ? "Not set" : formatQty(s.low_stock_threshold, s.unit)}
        />
      </dl>
      <p className="mt-1 text-text-muted">
        Used in: {s.used_in.length ? s.used_in.join(", ") : "no active dish"}
      </p>
      {editing === "adjust" ? (
        <AdjustForm stock={s} onDone={() => setEditing(null)} />
      ) : editing === "threshold" ? (
        <ThresholdForm stock={s} onDone={() => setEditing(null)} />
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => setEditing("adjust")}
            aria-label={`Adjust stock of ${s.name}`}
          >
            Adjust stock
          </Button>
          <Button
            variant="secondary"
            onClick={() => setEditing("threshold")}
            aria-label={`Set threshold for ${s.name}`}
          >
            Set threshold
          </Button>
        </div>
      )}
    </li>
  );
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt className="text-text-muted">{term}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function QuantityInput({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint: string;
}) {
  return (
    <div className="mt-3">
      <label htmlFor={id} className="block font-medium">
        {label}
      </label>
      <input
        id={id}
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 w-40 ${INPUT}`}
        aria-describedby={`${id}-hint`}
      />
      <p id={`${id}-hint`} className="text-xs text-text-muted">
        {hint}
      </p>
    </div>
  );
}

const QTY = /^-?\d+(\.\d{1,3})?$/;

function AdjustForm({ stock: s, onDone }: { stock: Stock; onDone: () => void }) {
  const adjust = useAdjustStock();
  const [delta, setDelta] = useState("");
  const valid = QTY.test(delta) && Number(delta) !== 0;
  return (
    <div>
      <QuantityInput
        id={`adj-${s.ingredient_id}`}
        label={`Change in ${s.unit}`}
        value={delta}
        onChange={setDelta}
        hint={`Use a minus sign to remove stock. Stock cannot go below the ${formatQty(s.reserved, s.unit)} reserved.`}
      />
      {valid ? (
        <ReasonForm
          label="Reason for the adjustment"
          confirmLabel="Save adjustment"
          hint="Recorded in the stock ledger and audit log."
          onCancel={onDone}
          onConfirm={async (reason) => {
            try {
              await adjust.mutateAsync({ ingredientId: s.ingredient_id, delta, reason });
              onDone();
            } catch (e) {
              throw new Error(refusalText(e), { cause: e });
            }
          }}
        />
      ) : (
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={onDone}>
            Cancel
          </Button>
          {delta && !valid ? (
            <p role="alert" className="text-sm">
              Enter a non-zero quantity with up to 3 decimals.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ThresholdForm({ stock: s, onDone }: { stock: Stock; onDone: () => void }) {
  const setThreshold = useSetThreshold();
  const [value, setValue] = useState(s.low_stock_threshold ?? "");
  const cleared = value.trim() === "";
  const valid = cleared || (QTY.test(value) && Number(value) >= 0);
  return (
    <div>
      <QuantityInput
        id={`thr-${s.ingredient_id}`}
        label={`Low-stock threshold in ${s.unit}`}
        value={value}
        onChange={setValue}
        hint="Leave empty to clear it: no alert is raised without a threshold."
      />
      {valid ? (
        <ReasonForm
          label="Reason for the threshold"
          confirmLabel={cleared ? "Clear threshold" : "Save threshold"}
          onCancel={onDone}
          onConfirm={async (reason) => {
            try {
              await setThreshold.mutateAsync({
                ingredientId: s.ingredient_id,
                threshold: cleared ? null : value,
                reason,
              });
              onDone();
            } catch (e) {
              throw new Error(refusalText(e), { cause: e });
            }
          }}
        />
      ) : (
        <p role="alert" className="mt-2 text-sm">
          Enter a quantity of 0 or more with up to 3 decimals.
        </p>
      )}
    </div>
  );
}

function LowStockList() {
  const low = useLowStock();
  const state = queryState(low, { loading: "Loading stock alerts…" });
  if (state) return state;
  const rows = low.data ?? [];
  return (
    <section aria-labelledby="low-stock">
      <h2 id="low-stock" className="text-xl font-semibold">
        Low-stock alerts ({rows.length})
      </h2>
      {rows.length === 0 ? (
        <EmptyState title="No low-stock alerts">The Kitchen Manager manages stock and thresholds.</EmptyState>
      ) : (
        <ul className="mt-3 space-y-2">
          {rows.map((s) => (
            <li key={s.ingredient_id} className="rounded-panel border border-border bg-surface p-3 text-sm">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {s.name} {s.is_test_fixture ? <TestBadge label="Test stock" /> : null}
              </p>
              <p>
                {formatQty(s.available, s.unit)} available · threshold{" "}
                {formatQty(s.low_stock_threshold, s.unit)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// KI-24, DDR-111 (7): the kitchen asks; only an RM or CA approval changes the customer menu.
function DishAvailability() {
  const queue = useKitchenQueue();
  const kitchenId = queue.data?.kitchen_id;
  const dishes = useKitchenDishes(kitchenId);
  const requests = useAvailabilityRequests(false);
  const request = useRequestAvailability();
  const [picked, setPicked] = useState<{ id: string; name: string; kind: AvailabilityKind } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const pending = new Set(
    (requests.data ?? []).filter((r) => r.status === "PENDING").map((r) => r.menu_item_id),
  );

  return (
    <section aria-labelledby="availability" className="space-y-3">
      <h2 id="availability" className="text-xl font-semibold">
        Dish availability
      </h2>
      <p className="text-sm text-text-muted">
        Ask to take a dish off the menu, or to bring it back. A Regional Manager decides.
      </p>
      {queryState(dishes, { loading: "Loading dishes…" }) ?? (
        <ul className="grid gap-2 lg:grid-cols-2" aria-label="Kitchen dishes">
          {(dishes.data ?? []).map((d) => {
            const kind: AvailabilityKind =
              d.publication_status === "PUBLISHED" ? "MAKE_UNAVAILABLE" : "MAKE_AVAILABLE";
            return (
              <li key={d.id} className="rounded-panel border border-border bg-surface p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {d.name} {d.is_test_fixture ? <TestBadge /> : null}
                  <StatusBadge
                    tone={d.publication_status === "PUBLISHED" ? "success" : "warning"}
                    label={d.publication_status === "PUBLISHED" ? "On the menu" : "Temporarily unavailable"}
                  />
                </p>
                {pending.has(d.id) ? (
                  <p className="mt-2">A request is waiting for a decision.</p>
                ) : picked?.id === d.id ? (
                  <ReasonForm
                    label={
                      kind === "MAKE_UNAVAILABLE"
                        ? `Why should ${d.name} come off the menu?`
                        : `Why can ${d.name} return?`
                    }
                    confirmLabel="Send request"
                    onCancel={() => setPicked(null)}
                    onConfirm={async (reason) => {
                      try {
                        await request.mutateAsync({ menu_item_id: d.id, kind, reason });
                        setPicked(null);
                        setDone(`Request sent for ${d.name}.`);
                      } catch (e) {
                        throw new Error(refusalText(e), { cause: e });
                      }
                    }}
                  />
                ) : (
                  <Button
                    variant="secondary"
                    className="mt-2"
                    onClick={() => setPicked({ id: d.id, name: d.name, kind })}
                  >
                    {kind === "MAKE_UNAVAILABLE" ? "Request unavailable" : "Request available again"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {done ? <p role="status">{done}</p> : null}
      <h3 className="text-lg font-semibold">Requests</h3>
      {queryState(requests, { loading: "Loading requests…" }) ?? (
        <AvailabilityList rows={requests.data ?? []} />
      )}
    </section>
  );
}
