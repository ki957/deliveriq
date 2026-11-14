import { useId, useState, type FormEvent } from "react";

import { csvHref, useAudit, useRegions, type AuditFilters } from "../api";
import { dayBound, PageHeader, Pager, TableBox, Td, Th } from "./common";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { formatDateTime, humanize } from "@/shared/utils/format";

const ROLES = [
  "CUSTOMER",
  "KITCHEN_STAFF",
  "KITCHEN_MANAGER",
  "DELIVERY_AGENT",
  "REGIONAL_MANAGER",
  "CENTRAL_ADMIN",
  "SYSTEM",
];

type Form = { action: string; target: string; role: string; from: string; to: string };
const EMPTY: Form = { action: "", target: "", role: "", from: "", to: "" };

function toFilters(f: Form): AuditFilters {
  return {
    action: f.action.trim() || undefined,
    target_type: f.target.trim() || undefined,
    actor_role: f.role || undefined,
    date_from: dayBound(f.from, false),
    date_to: dayBound(f.to, true),
  };
}

// #10 §12, DDR-114 (7), (8): RM sees events of own regions, CA all (including events with no region).
// Filters action, target, actor role, date range ≤ 31 days; 50 per page; audited CSV export.
export function AuditPage({ title }: { title: string }) {
  const [form, setForm] = useState<Form>(EMPTY);
  const [applied, setApplied] = useState<AuditFilters>({});
  const [page, setPage] = useState(1);
  const audit = useAudit(page, applied);
  const regions = useRegions();
  const id = useId();
  const regionName = new Map((regions.data ?? []).map((r) => [r.id, r.name]));

  function apply(event: FormEvent) {
    event.preventDefault();
    setApplied(toFilters(form));
    setPage(1);
  }

  const state = queryState(audit, { loading: "Loading audit log…" });
  return (
    <section className="mx-auto max-w-6xl space-y-4">
      <PageHeader title={title} />
      <form
        onSubmit={apply}
        aria-label="Audit filters"
        className="grid gap-3 rounded-panel border border-border bg-surface p-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <div>
          <label htmlFor={`${id}-action`} className="block text-sm font-medium">
            Action
          </label>
          <input
            id={`${id}-action`}
            value={form.action}
            maxLength={80}
            placeholder="e.g. management.staff.role_granted"
            onChange={(e) => setForm({ ...form, action: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-target`} className="block text-sm font-medium">
            Target type
          </label>
          <input
            id={`${id}-target`}
            value={form.target}
            maxLength={60}
            placeholder="e.g. order"
            onChange={(e) => setForm({ ...form, target: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-role`} className="block text-sm font-medium">
            Actor role
          </label>
          <select
            id={`${id}-role`}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          >
            <option value="">Any</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {humanize(r)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-from`} className="block text-sm font-medium">
            From
          </label>
          <input
            id={`${id}-from`}
            type="date"
            value={form.from}
            onChange={(e) => setForm({ ...form, from: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-to`} className="block text-sm font-medium">
            To
          </label>
          <input
            id={`${id}-to`}
            type="date"
            value={form.to}
            onChange={(e) => setForm({ ...form, to: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <p className="text-xs text-text-muted sm:col-span-3 lg:col-span-3">
          Without dates the last 7 days are shown; a range can be at most 31 days.
        </p>
        <div className="flex flex-wrap gap-2 sm:col-span-3 lg:col-span-2 lg:justify-end">
          <Button type="submit">Apply filters</Button>
          <Button asChild variant="secondary">
            <a href={csvHref("audit.csv", applied)} download>
              Export CSV
            </a>
          </Button>
        </div>
      </form>

      {state ??
        (audit.data && audit.data.rows.length > 0 ? (
          <>
            <TableBox label="Audit events">
              <thead className="bg-muted">
                <tr>
                  <Th>When</Th>
                  <Th>Actor</Th>
                  <Th>Action</Th>
                  <Th>Target</Th>
                  <Th>Region</Th>
                  <Th>Outcome</Th>
                  <Th>Reason</Th>
                </tr>
              </thead>
              <tbody>
                {audit.data.rows.map((r, n) => (
                  <tr key={`${r.occurred_at}-${n}`} className="border-t border-border">
                    <Td>{formatDateTime(r.occurred_at)}</Td>
                    <Td>
                      {r.actor_name ?? "System"}
                      <span className="block text-xs text-text-muted">{humanize(r.actor_role)}</span>
                    </Td>
                    <Td>
                      <code className="text-xs">{r.action}</code>
                    </Td>
                    <Td>
                      {r.target_type}
                      {r.target_id ? (
                        <span className="block text-xs text-text-muted">{r.target_id.slice(0, 12)}</span>
                      ) : null}
                    </Td>
                    <Td>{r.region_id ? (regionName.get(r.region_id) ?? "Region") : "No region"}</Td>
                    <Td>{humanize(r.outcome)}</Td>
                    <Td>{r.reason ?? "—"}</Td>
                  </tr>
                ))}
              </tbody>
            </TableBox>
            <Pager
              page={audit.data.page}
              pageSize={audit.data.page_size}
              total={audit.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <p className="text-sm">No audit events match these filters in your scope.</p>
        ))}
    </section>
  );
}
