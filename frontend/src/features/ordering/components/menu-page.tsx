import { useMemo, useState } from "react";
import { Link } from "react-router";

import { useMenu, useMenuFilters, useServiceability, type MenuItem, type MenuQuery } from "../api";
import { useChosenLocation } from "../location";
import { LocationPanel } from "./location-panel";
import { DishImage, VegMark } from "./dish-bits";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { TestBadge } from "@/shared/ui/test-badge";
import { INPUT } from "@/shared/ui/input";
import { formatPaise } from "@/shared/utils/format";

// CU-06/07: menu with categories, search and filters; only after a serviceable location (CU-01, CU-04).
export function MenuPage() {
  const [location] = useChosenLocation();
  const reach = useServiceability(location);
  const serviceable = Boolean(reach.data?.serviceable);

  return (
    <section className="mx-auto max-w-6xl">
      <h1 className="text-2xl font-semibold">Menu</h1>
      <div className="mt-4">
        <LocationPanel />
      </div>
      {location ? <div className="mt-4">{queryState(reach, { loading: "Checking delivery…" })}</div> : null}
      {location && serviceable ? <Catalogue /> : null}
      {location && reach.data && !serviceable ? (
        <p className="mt-4 text-sm text-text-muted">
          The menu is shown once you choose a location we deliver to.
        </p>
      ) : null}
    </section>
  );
}

function Catalogue() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [veg, setVeg] = useState("");
  const [spice, setSpice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [bestseller, setBestseller] = useState(false);
  const filters = useMenuFilters(true);
  const query = useMemo<MenuQuery>(() => {
    const out: MenuQuery = {};
    if (q.trim()) out.q = q.trim();
    if (category) out.category = category;
    if (veg) out.veg = veg === "veg";
    if (spice) out.spice = spice;
    if (maxPrice) out.max_price_paise = Number(maxPrice) * 100;
    if (bestseller) out.bestseller = true;
    return out;
  }, [q, category, veg, spice, maxPrice, bestseller]);
  const menu = useMenu(query, true);
  const f = filters.data;

  return (
    <div className="mt-6">
      <form
        role="search"
        aria-label="Menu filters"
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <Field id="menu-q" label="Search dishes">
          <input
            id="menu-q"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className={INPUT}
          />
        </Field>
        <Field id="menu-category" label="Category">
          <select
            id="menu-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={INPUT}
          >
            <option value="">All categories</option>
            {f?.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field id="menu-veg" label="Veg / non-veg">
          <select id="menu-veg" value={veg} onChange={(e) => setVeg(e.target.value)} className={INPUT}>
            <option value="">All</option>
            {f?.has_veg ? <option value="veg">Vegetarian</option> : null}
            {f?.has_non_veg ? <option value="nonveg">Non-vegetarian</option> : null}
          </select>
        </Field>
        <Field id="menu-spice" label="Spice level">
          <select id="menu-spice" value={spice} onChange={(e) => setSpice(e.target.value)} className={INPUT}>
            <option value="">Any</option>
            {f?.spice_levels.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field id="menu-price" label="Max price (₹)">
          <input
            id="menu-price"
            inputMode="numeric"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value.replace(/\D/g, ""))}
            className={`w-28 ${INPUT}`}
          />
        </Field>
        {f?.has_bestsellers ? (
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-5"
              checked={bestseller}
              onChange={(e) => setBestseller(e.target.checked)}
            />
            Bestsellers only
          </label>
        ) : null}
      </form>
      <div className="mt-4">
        {queryState(menu, { loading: "Loading the menu…" }) ?? <DishGrid items={menu.data ?? []} />}
      </div>
    </div>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function DishGrid({ items }: { items: MenuItem[] }) {
  if (items.length === 0) return <EmptyState title="No dishes match these filters" />;
  return (
    <ul aria-label="Dishes" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <li key={item.id} className="overflow-hidden rounded-panel border border-border bg-surface">
          <DishImage item={item} />
          <div className="p-3">
            <div className="flex flex-wrap items-center gap-2">
              <VegMark isVeg={item.is_veg} />
              {item.is_test_fixture ? <TestBadge /> : null}
            </div>
            <h2 className="mt-1 font-semibold">
              <Link to={`/customer/menu/${item.id}`} className="underline">
                {item.name}
              </Link>
            </h2>
            {item.description ? <p className="mt-1 text-sm text-text-muted">{item.description}</p> : null}
            <p className="mt-2 font-semibold">{formatPaise(item.price_paise)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
