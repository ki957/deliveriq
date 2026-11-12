import { useMemo, useState } from "react";
import { Link } from "react-router";

import { useVersions, type RecipeStatus } from "../api";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { recipeStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";

const STATUSES: RecipeStatus[] = [
  "DRAFT",
  "PENDING_VALIDATION",
  "VALIDATED",
  "ACTIVE",
  "REJECTED",
  "QUARANTINED_DUPLICATE_CANDIDATE",
];

// Kitchen → Recipes (KI-17, KI-20): SOP recipes stay DRAFT; TEST recipes demonstrate the workflow (DDR-50).
export function RecipesPage() {
  const versions = useVersions();
  const [status, setStatus] = useState<RecipeStatus | "ALL">("ALL");
  const [search, setSearch] = useState("");
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (versions.data ?? []).filter(
      (v) =>
        (status === "ALL" || v.status === status) &&
        (!q || v.name.toLowerCase().includes(q) || (v.source_menu_id ?? "").toLowerCase().includes(q)),
    );
  }, [versions.data, status, search]);

  const state = queryState(versions, { loading: "Loading recipes…" });
  if (state) return state;

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Recipes</h1>
      <p className="mt-1 text-sm text-text-muted">
        SOP recipes are imported as drafts and are never activated in this POC. TEST recipes show the full
        approval workflow.
      </p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="recipe-search" className="block text-sm font-medium">
            Search by name or card ID
          </label>
          <input
            id="recipe-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
          />
        </div>
        <div>
          <label htmlFor="recipe-status" className="block text-sm font-medium">
            Status
          </label>
          <select
            id="recipe-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as RecipeStatus | "ALL")}
            className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
          >
            <option value="ALL">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {recipeStatus(s)[1]}
              </option>
            ))}
          </select>
        </div>
        <p className="text-sm text-text-muted" role="status">
          {rows.length} of {versions.data?.length ?? 0} recipes
        </p>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No recipes match" />
      ) : (
        <div className="mt-4 overflow-x-auto rounded-panel border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted">
              <tr>
                <th scope="col" className="p-2">
                  Recipe
                </th>
                <th scope="col" className="p-2">
                  Card
                </th>
                <th scope="col" className="p-2">
                  Status
                </th>
                <th scope="col" className="p-2">
                  Open review items
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => (
                <tr key={v.id} className="border-t border-border">
                  <td className="p-2">
                    <span className="flex flex-wrap items-center gap-2">
                      <Link to={`/kitchen/recipes/${v.id}`} className="underline">
                        {v.name}
                      </Link>
                      {v.is_test_fixture ? <TestBadge /> : null}
                    </span>
                  </td>
                  <td className="p-2">{v.source_menu_id ?? "—"}</td>
                  <td className="p-2">
                    <StatusBadge tone={recipeStatus(v.status)[0]} label={recipeStatus(v.status)[1]} />
                  </td>
                  <td className="p-2">{v.open_review_items || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
