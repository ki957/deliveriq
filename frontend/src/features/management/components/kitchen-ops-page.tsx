import { useState } from "react";
import { Link } from "react-router";

import { useKitchens } from "../api";
import { KitchenPicker, PageHeader } from "./common";
import { KitchenTable } from "./overview-page";
import { KitchenSettingsPanel } from "@/features/kitchen";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";

// DDR-114 (2): kitchens in scope with intake, and mode/capacity through the existing kitchen settings
// API (RM own regions, CA all; reason required and audited, DDR-111 (14)).
export function KitchenOpsPage() {
  const kitchens = useKitchens();
  const [picked, setPicked] = useState("");
  const state = queryState(kitchens, { loading: "Loading kitchens…" });
  if (state) return state;
  const list = kitchens.data ?? [];
  const kitchenId = picked || list[0]?.id || "";
  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Kitchen Operations" updatedAt={kitchens.dataUpdatedAt} />
      {list.length === 0 ? (
        <EmptyState title="No kitchens in your scope" />
      ) : (
        <>
          <KitchenTable kitchens={list} />
          <section aria-labelledby="kitchen-settings" className="space-y-3">
            <h2 id="kitchen-settings" className="sr-only">
              Kitchen settings
            </h2>
            <KitchenPicker kitchens={list} value={kitchenId} onChange={setPicked} />
            <KitchenSettingsPanel key={kitchenId} kitchenId={kitchenId} />
          </section>
          <p className="text-sm">
            Dish availability requests are decided in{" "}
            <Link to="/management/dish-availability" className="underline">
              Dish Availability
            </Link>
            . Orders the kitchen cannot fulfil are handled in{" "}
            <Link to="/management/orders" className="underline">
              Orders &amp; Exceptions
            </Link>
            .
          </p>
        </>
      )}
    </section>
  );
}
