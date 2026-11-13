import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";

import {
  Refusal,
  useAcceptPrice,
  useAddAddress,
  useAddresses,
  useCart,
  usePlaceOrder,
  useRemoveLine,
  useRemoveUnavailable,
  useSetQuantity,
  type Address,
  type Cart,
  type CartLine,
  type PaymentMethod,
} from "../api";
import { describe, minimumGap } from "../messages";
import { ServiceabilitySummary } from "./location-panel";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatPaise } from "@/shared/utils/format";
import { INPUT } from "@/shared/ui/input";

const METHODS: { value: PaymentMethod; label: string }[] = [
  // #15 §9 display names. No real payment is made (CU-29).
  { value: "SIM_UPI", label: "UPI (Simulation)" },
  { value: "SIM_CARD", label: "Card (Simulation)" },
  { value: "COD", label: "Cash on Delivery" },
];
const INSTRUCTIONS_MAX = 250; // DDR-07; the backend refuses 251

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

// Cart and checkout (CU-11–CU-18): the bill, blockers and placement all come from the backend quote.
export function CartPage() {
  const addresses = useAddresses(true);
  const [picked, setAddressId] = useState<string | null>(null);
  const [couponInput, setCouponInput] = useState("");
  const [coupon, setCoupon] = useState<string | null>(null);
  // Until the customer picks one, use the default address (or the first saved one).
  const fallback = addresses.data?.find((a) => a.is_default) ?? addresses.data?.[0];
  const addressId = picked ?? fallback?.id ?? null;
  const cart = useCart(addressId, coupon);

  const state = queryState(cart, { loading: "Loading your cart…" });
  if (state) return state;
  if (!cart.data) return null;
  const data = cart.data;

  if (data.lines.length === 0) {
    return (
      <section className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">Cart</h1>
        <EmptyState title="Your cart is empty">
          <Link to="/customer/menu" className="underline">
            Browse the menu
          </Link>
        </EmptyState>
      </section>
    );
  }

  return (
    <section className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_22rem]">
      <div>
        <h1 className="text-2xl font-semibold">Cart</h1>
        <Lines cart={data} />
        <AddressChoice
          addresses={addresses.data ?? []}
          value={addressId}
          onChange={setAddressId}
          cart={data}
        />
      </div>
      <aside aria-label="Checkout" className="space-y-4">
        <CouponBox
          value={couponInput}
          onChange={setCouponInput}
          onApply={() => setCoupon(couponInput.trim() || null)}
          applied={data.coupon_code}
          error={data.coupon_error}
          onClear={() => {
            setCoupon(null);
            setCouponInput("");
          }}
        />
        <BillBox cart={data} />
        <Checkout cart={data} addressId={addressId} coupon={data.coupon_error ? null : data.coupon_code} />
      </aside>
    </section>
  );
}

function Lines({ cart }: { cart: Cart }) {
  const setQuantity = useSetQuantity();
  const remove = useRemoveLine();
  const accept = useAcceptPrice();
  const removeUnavailable = useRemoveUnavailable();
  const [confirming, setConfirming] = useState(false);
  const unavailable = cart.lines.filter((l) => !l.available);

  return (
    <div className="mt-4 space-y-3">
      {unavailable.length > 0 ? (
        <div role="alert" className="rounded-panel border border-status-warning bg-surface p-3 text-sm">
          <p className="font-medium">
            {unavailable.map((l) => l.name).join(", ")} {unavailable.length === 1 ? "is" : "are"} no longer
            available.
          </p>
          {confirming ? (
            <div className="mt-2 flex flex-wrap gap-2">
              <Button onClick={() => removeUnavailable.mutate(true)} disabled={removeUnavailable.isPending}>
                Confirm removal
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                Keep for now
              </Button>
            </div>
          ) : (
            <Button variant="secondary" className="mt-2" onClick={() => setConfirming(true)}>
              Remove unavailable dishes
            </Button>
          )}
        </div>
      ) : null}
      <ul
        aria-label="Cart items"
        className="divide-y divide-border rounded-panel border border-border bg-surface"
      >
        {cart.lines.map((line) => (
          <LineRow
            key={line.menu_item_id}
            line={line}
            onQuantity={(q) => setQuantity.mutate({ id: line.menu_item_id, quantity: q })}
            onRemove={() => remove.mutate(line.menu_item_id)}
            onAccept={() => accept.mutate(line.menu_item_id)}
            busy={setQuantity.isPending || remove.isPending || accept.isPending}
          />
        ))}
      </ul>
    </div>
  );
}

function LineRow({
  line,
  onQuantity,
  onRemove,
  onAccept,
  busy,
}: {
  line: CartLine;
  onQuantity: (q: number) => void;
  onRemove: () => void;
  onAccept: () => void;
  busy: boolean;
}) {
  const charge = line.charge_price_paise ?? line.cart_price_paise;
  return (
    <li className="p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="flex flex-wrap items-center gap-2 font-medium">
            {line.name}
            {line.is_test_fixture ? <TestBadge /> : null}
          </p>
          <p className="text-text-muted">
            {formatPaise(charge)} each
            {line.available && !line.price_changed
              ? ` · price held until ${formatDateTime(line.protected_until)}`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            aria-label={`One less ${line.name}`}
            disabled={busy || line.quantity <= 1}
            onClick={() => onQuantity(line.quantity - 1)}
          >
            −
          </Button>
          <span aria-label={`Quantity of ${line.name}`} className="w-8 text-center">
            {line.quantity}
          </span>
          <Button
            variant="secondary"
            aria-label={`One more ${line.name}`}
            disabled={busy || !line.available || line.quantity >= 99}
            onClick={() => onQuantity(line.quantity + 1)}
          >
            +
          </Button>
          <Button variant="ghost" onClick={onRemove} disabled={busy}>
            Remove
          </Button>
        </div>
      </div>
      {line.price_changed ? (
        <div role="alert" className="mt-2 rounded-control border border-status-warning p-2">
          <p>
            The price changed from {formatPaise(line.cart_price_paise)} to{" "}
            {formatPaise(line.charge_price_paise)}.
          </p>
          <Button variant="secondary" className="mt-2" onClick={onAccept} disabled={busy}>
            Accept new price
          </Button>
        </div>
      ) : null}
    </li>
  );
}

function AddressChoice({
  addresses,
  value,
  onChange,
  cart,
}: {
  addresses: Address[];
  value: string | null;
  onChange: (id: string) => void;
  cart: Cart;
}) {
  const [adding, setAdding] = useState(false);
  return (
    <fieldset className="mt-6 rounded-panel border border-border bg-surface p-4">
      <legend className="px-1 text-lg font-semibold">Delivery address</legend>
      {addresses.length > 0 ? (
        <ul className="space-y-2">
          {addresses.map((a) => (
            <li key={a.id}>
              <label className="flex min-h-11 items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="address"
                  className="mt-1 size-5"
                  checked={value === a.id}
                  onChange={() => onChange(a.id)}
                />
                <span>
                  <span className="font-medium">{a.label}</span>
                  {a.is_default ? " (default)" : ""} · {a.address_line}
                </span>
              </label>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-muted">Add an address to check delivery and place your order.</p>
      )}
      {cart.serviceability ? (
        <div className="mt-3">
          <ServiceabilitySummary reach={cart.serviceability} />
        </div>
      ) : null}
      {adding ? (
        <NewAddress
          onDone={(id) => {
            setAdding(false);
            if (id) onChange(id);
          }}
        />
      ) : (
        <Button variant="secondary" className="mt-3" onClick={() => setAdding(true)}>
          Add an address
        </Button>
      )}
    </fieldset>
  );
}

function NewAddress({ onDone }: { onDone: (id: string | null) => void }) {
  const add = useAddAddress();
  const [error, setError] = useState<string | null>(null);
  const [coords, setCoords] = useState<{ lat: string; lng: string }>({ lat: "", lng: "" });

  function locate() {
    setError(null);
    navigator.geolocation?.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude.toFixed(6), lng: pos.coords.longitude.toFixed(6) }),
      () => setError("Location access was denied or unavailable. Enter coordinates instead."),
      { timeout: 10_000 },
    );
  }

  async function save(form: HTMLFormElement) {
    const data = new FormData(form);
    const lat = Number(coords.lat);
    const lng = Number(coords.lng);
    if (!coords.lat || !coords.lng || !Number.isFinite(lat) || !Number.isFinite(lng)) {
      setError("Use your current location or enter a latitude and longitude.");
      return;
    }
    try {
      const created = await add.mutateAsync({
        label: String(data.get("label") || "Home"),
        address_line: String(data.get("line") ?? ""),
        lat,
        lng,
        make_default: data.get("default") === "on",
      });
      onDone(created.id);
    } catch {
      setError("Check the address details and coordinates (they must be in India).");
    }
  }

  return (
    <form
      className="mt-3 grid gap-3 sm:grid-cols-2"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void save(e.currentTarget);
      }}
    >
      <div>
        <label htmlFor="addr-label" className="block text-sm font-medium">
          Label
        </label>
        <input
          id="addr-label"
          name="label"
          maxLength={40}
          placeholder="Home"
          className={`mt-1 w-full ${INPUT}`}
        />
      </div>
      <div>
        <label htmlFor="addr-line" className="block text-sm font-medium">
          Address
        </label>
        <input
          id="addr-line"
          name="line"
          required
          minLength={3}
          maxLength={300}
          className={`mt-1 w-full ${INPUT}`}
        />
      </div>
      <div>
        <label htmlFor="addr-lat" className="block text-sm font-medium">
          Latitude
        </label>
        <input
          id="addr-lat"
          inputMode="decimal"
          value={coords.lat}
          onChange={(e) => setCoords({ ...coords, lat: e.target.value })}
          className={`mt-1 w-full ${INPUT}`}
        />
      </div>
      <div>
        <label htmlFor="addr-lng" className="block text-sm font-medium">
          Longitude
        </label>
        <input
          id="addr-lng"
          inputMode="decimal"
          value={coords.lng}
          onChange={(e) => setCoords({ ...coords, lng: e.target.value })}
          className={`mt-1 w-full ${INPUT}`}
        />
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" name="default" className="size-5" /> Make this my default address
      </label>
      <div className="flex flex-wrap gap-2 sm:col-span-2">
        <Button variant="secondary" onClick={locate}>
          Use my current location
        </Button>
        <Button type="submit" disabled={add.isPending}>
          Save address
        </Button>
        <Button variant="ghost" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm sm:col-span-2">
          {error}
        </p>
      ) : null}
    </form>
  );
}

function CouponBox({
  value,
  onChange,
  onApply,
  applied,
  error,
  onClear,
}: {
  value: string;
  onChange: (v: string) => void;
  onApply: () => void;
  applied: string | null;
  error: string | null;
  onClear: () => void;
}) {
  return (
    <form
      className="rounded-panel border border-border bg-surface p-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        onApply();
      }}
    >
      <label htmlFor="coupon" className="block text-sm font-medium">
        Coupon code
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id="coupon"
          value={value}
          maxLength={20}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full uppercase ${INPUT}`}
        />
        <Button type="submit" variant="secondary">
          Apply
        </Button>
      </div>
      {applied && !error ? (
        <p role="status" className="mt-2 flex items-center justify-between text-sm">
          Coupon {applied} applied.
          <Button variant="ghost" onClick={onClear}>
            Remove
          </Button>
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 text-sm">
          {describe(error)}
        </p>
      ) : null}
    </form>
  );
}

function BillBox({ cart }: { cart: Cart }) {
  const b = cart.bill;
  const gap = minimumGap(b.food_subtotal_paise, b.minimum_food_subtotal_paise);
  return (
    <section aria-labelledby="bill" className="rounded-panel border border-border bg-surface p-4 text-sm">
      <h2 id="bill" className="text-lg font-semibold">
        Bill
      </h2>
      <dl className="mt-2 space-y-1">
        <Row term="Food subtotal" value={formatPaise(b.food_subtotal_paise)} />
        <Row term="Delivery fee" value={formatPaise(b.delivery_fee_paise)} />
        {b.discount_paise ? <Row term="Coupon" value={`− ${formatPaise(b.discount_paise)}`} /> : null}
        <Row term="To pay" value={formatPaise(b.payable_paise)} strong />
      </dl>
      <p className="mt-2 text-xs text-text-muted">{b.tax_note}</p>
      {gap ? (
        <p className="mt-2 text-sm" data-testid="minimum-gap">
          {gap}
        </p>
      ) : null}
    </section>
  );
}

function Row({ term, value, strong = false }: { term: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between ${strong ? "border-t border-border pt-1 font-semibold" : ""}`}>
      <dt>{term}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Checkout({
  cart,
  addressId,
  coupon,
}: {
  cart: Cart;
  addressId: string | null;
  coupon: string | null;
}) {
  const place = usePlaceOrder();
  const navigate = useNavigate();
  const [method, setMethod] = useState<PaymentMethod>("SIM_UPI");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  // One key per checkout attempt: a retried request returns the same order (DDR-109).
  const [key, setKey] = useState(newKey);
  const blockers = useMemo(() => cart.blockers.filter((b) => !b.startsWith("coupon_")), [cart.blockers]);
  const isTest = cart.lines.length > 0 && cart.lines.every((l) => l.is_test_fixture);

  async function submit() {
    setError(null);
    if (!addressId) return;
    try {
      const order = await place.mutateAsync({
        key,
        body: {
          lines: cart.lines.map((l) => ({
            menu_item_id: l.menu_item_id,
            quantity: l.quantity,
            unit_price_paise: l.charge_price_paise ?? l.cart_price_paise,
          })),
          payment_method: method,
          address_id: addressId,
          special_instructions: instructions.trim() || null,
          coupon_code: coupon,
        },
      });
      navigate(`/customer/orders/${order.id}`);
    } catch (e) {
      // Nothing was created: a new attempt gets a new key.
      setKey(newKey());
      setError(e instanceof Refusal ? describe(e.code, e.message) : "Something went wrong. Try again.");
    }
  }

  return (
    <section aria-labelledby="pay" className="rounded-panel border border-border bg-surface p-4 text-sm">
      <h2 id="pay" className="text-lg font-semibold">
        Payment
      </h2>
      <fieldset className="mt-2">
        <legend className="sr-only">Payment method</legend>
        {METHODS.map((m) => (
          <label key={m.value} className="flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name="method"
              className="size-5"
              checked={method === m.value}
              onChange={() => setMethod(m.value)}
            />
            {m.label}
          </label>
        ))}
      </fieldset>
      <p className="text-xs text-text-muted">Payments are simulated. No real money is charged.</p>
      <label htmlFor="instructions" className="mt-3 block font-medium">
        Special instructions (optional)
      </label>
      <textarea
        id="instructions"
        value={instructions}
        maxLength={INSTRUCTIONS_MAX}
        rows={3}
        onChange={(e) => setInstructions(e.target.value)}
        aria-describedby="instructions-count"
        className="mt-1 w-full rounded-control border border-border bg-surface px-3 py-2"
      />
      <p id="instructions-count" className="text-xs text-text-muted">
        {instructions.length} / {INSTRUCTIONS_MAX} characters
      </p>
      {blockers.length > 0 ? (
        <ul aria-label="Before you can order" className="mt-3 list-inside list-disc space-y-1">
          {blockers.map((b) => (
            <li key={b}>{describe(b)}</li>
          ))}
        </ul>
      ) : null}
      {isTest ? (
        <p className="mt-3 flex items-center gap-2">
          <TestBadge label="Test order" /> This order uses TEST dishes.
        </p>
      ) : null}
      <Button className="mt-3 w-full" onClick={submit} disabled={blockers.length > 0 || place.isPending}>
        Place order · {formatPaise(cart.bill.payable_paise)}
      </Button>
      {error ? (
        <p role="alert" className="mt-2 rounded-control border border-status-danger p-2">
          {error}
        </p>
      ) : null}
    </section>
  );
}
