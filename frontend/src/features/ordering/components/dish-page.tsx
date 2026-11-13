import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useDish, useSetQuantity, Refusal } from "../api";
import { describe } from "../messages";
import { DishImage, VegMark } from "./dish-bits";
import { useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatPaise } from "@/shared/utils/format";

// CU-08: description, ingredients, base price, customization (none configured yet, DDR-110 (10)).
// Dishes are added here; the food-card Add interaction waits for DDR-06.
export function DishPage() {
  const { dishId = "" } = useParams();
  const dish = useDish(dishId);
  const me = useMe();
  const add = useSetQuantity();
  const navigate = useNavigate();
  // Keep what the customer typed; it is checked on Add (the backend also enforces 1–99).
  const [quantityText, setQuantityText] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const state = queryState(dish, { loading: "Loading dish…", notFound: "This dish is not available" });
  if (state) return state;
  if (!dish.data) return null;
  const d = dish.data;

  async function addToCart() {
    setError(null);
    const quantity = Number(quantityText);
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99) {
      setError("Enter a quantity from 1 to 99.");
      return;
    }
    try {
      await add.mutateAsync({ id: d.id, quantity });
      navigate("/customer/cart");
    } catch (e) {
      setError(e instanceof Refusal ? describe(e.code, e.message) : "Something went wrong. Try again.");
    }
  }

  return (
    <article className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2">
      <div className="self-start overflow-hidden rounded-panel border border-border">
        <DishImage item={d} />
      </div>
      <div>
        <p className="text-sm">
          <Link to="/customer/menu" className="underline">
            Menu
          </Link>
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <VegMark isVeg={d.is_veg} />
          {d.is_test_fixture ? <TestBadge /> : null}
          {d.spice_level ? (
            <span className="text-xs text-text-muted">Spice level: {d.spice_level}</span>
          ) : null}
        </div>
        <h1 className="mt-2 text-2xl font-semibold">{d.name}</h1>
        {d.description ? <p className="mt-2 text-text-muted">{d.description}</p> : null}
        <p className="mt-3 text-xl font-semibold">{formatPaise(d.price_paise)}</p>
        <p className="text-xs text-text-muted">Prices include applicable taxes.</p>
        <section aria-labelledby="ingredients" className="mt-4">
          <h2 id="ingredients" className="font-semibold">
            Ingredients
          </h2>
          {d.ingredients.length ? (
            <ul className="mt-1 list-inside list-disc text-sm">
              {d.ingredients.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-text-muted">Not listed.</p>
          )}
        </section>
        <section aria-labelledby="customization" className="mt-4">
          <h2 id="customization" className="font-semibold">
            Customization
          </h2>
          <p className="mt-1 text-sm text-text-muted">No customization options are set for this dish.</p>
        </section>
        {me.data ? (
          <div className="mt-6 flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor="dish-qty" className="block text-sm font-medium">
                Quantity
              </label>
              <input
                id="dish-qty"
                type="number"
                min={1}
                max={99}
                step={1}
                value={quantityText}
                onChange={(e) => setQuantityText(e.target.value)}
                className="mt-1 min-h-11 w-24 rounded-control border border-border bg-surface px-3"
              />
            </div>
            <Button onClick={addToCart} disabled={add.isPending}>
              Add to cart
            </Button>
          </div>
        ) : (
          <div className="mt-6 rounded-panel border border-border bg-muted p-4">
            <p className="font-medium">Sign in with your mobile number to order.</p>
            <Button asChild className="mt-3">
              <Link to={`/customer/login?next=${encodeURIComponent(`/customer/menu/${d.id}`)}`}>Sign in</Link>
            </Button>
          </div>
        )}
        {error ? (
          <p role="alert" className="mt-3 rounded-control border border-status-danger p-3 text-sm">
            {error}
          </p>
        ) : null}
      </div>
    </article>
  );
}
