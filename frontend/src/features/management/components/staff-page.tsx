import { useId, useState, type FormEvent, type ReactNode } from "react";

import {
  useAddStaff,
  useKitchens,
  useRegions,
  useRemoveRole,
  useSetStaffStatus,
  useStaff,
  type Staff,
  type StaffIn,
} from "../api";
import { PageHeader, ReasonAction } from "./common";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { formatDateTime, humanize } from "@/shared/utils/format";

type Role = StaffIn["role"];
const KITCHEN_ROLES: Role[] = ["KITCHEN_STAFF", "KITCHEN_MANAGER"];
const ROLE_LABEL: Record<Role, string> = {
  KITCHEN_STAFF: "Kitchen Staff",
  KITCHEN_MANAGER: "Kitchen Manager",
  DELIVERY_AGENT: "Delivery Agent",
  REGIONAL_MANAGER: "Regional Manager",
};

// #10 §4, DDR-114 (3)–(5): RM manages Kitchen Staff, Kitchen Managers and agents in own regions; CA also
// manages Regional Managers; no CA is created here. Nobody changes their own access. Every change needs
// a reason, is audited and ends the person's sessions at once. The backend enforces all of it.
export function StaffPage({ title }: { title: string }) {
  const staff = useStaff();
  const regions = useRegions();
  const kitchens = useKitchens();
  const state = queryState(staff, { loading: "Loading staff…" });
  if (state) return state;
  const regionName = new Map((regions.data ?? []).map((r) => [r.id, r.name]));
  const kitchenName = new Map((kitchens.data ?? []).map((k) => [k.id, k.name]));
  const people = groupByPerson(staff.data ?? []);
  return (
    <section className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={title}>
        <p className="text-sm text-text-muted">
          New staff sign in with their mobile number and a one-time code. Removing a role or deactivating an
          account signs the person out everywhere at once.
        </p>
      </PageHeader>
      <AddStaff />
      <section aria-labelledby="people" className="space-y-2">
        <h2 id="people" className="text-lg font-semibold">
          Staff
        </h2>
        {people.length === 0 ? (
          <EmptyState title="No staff in your scope" />
        ) : (
          <ul className="space-y-3" aria-label="Staff">
            {people.map((p) => (
              <Person key={p.userId} person={p} regionName={regionName} kitchenName={kitchenName} />
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

type PersonGroup = { userId: string; name: string; mobile: string; status: string; grants: Staff[] };

function groupByPerson(rows: Staff[]): PersonGroup[] {
  const map = new Map<string, PersonGroup>();
  for (const r of rows) {
    const g = map.get(r.user_id) ?? {
      userId: r.user_id,
      name: r.display_name,
      mobile: r.mobile_masked,
      status: r.user_status,
      grants: [],
    };
    g.grants.push(r);
    map.set(r.user_id, g);
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function Person({
  person,
  regionName,
  kitchenName,
}: {
  person: PersonGroup;
  regionName: Map<string, string>;
  kitchenName: Map<string, string>;
}) {
  const me = useMe();
  const remove = useRemoveRole();
  const setStatus = useSetStaffStatus();
  const self = me.data?.user_id === person.userId;
  const active = person.status === "ACTIVE";
  return (
    <li className="space-y-2 rounded-panel border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>
          <span className="font-medium">{person.name}</span>{" "}
          <span className="text-sm text-text-muted">{person.mobile}</span>{" "}
          <StatusBadge tone={active ? "success" : "neutral"} label={humanize(person.status)} />
          {self ? <span className="ml-2 text-sm">(you)</span> : null}
        </span>
        {self ? null : active ? (
          <ReasonAction
            label="Deactivate"
            prompt={`Why are you deactivating ${person.name}?`}
            confirmLabel="Deactivate"
            onConfirm={(reason) => setStatus.mutateAsync({ userId: person.userId, active: false, reason })}
          />
        ) : (
          <ReasonAction
            label="Reactivate"
            prompt={`Why are you reactivating ${person.name}?`}
            confirmLabel="Reactivate"
            onConfirm={(reason) => setStatus.mutateAsync({ userId: person.userId, active: true, reason })}
          />
        )}
      </div>
      <ul className="space-y-2" aria-label={`Roles of ${person.name}`}>
        {person.grants.map((g) => (
          <li key={g.assignment_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span>
              {ROLE_LABEL[g.role as Role] ?? humanize(g.role)} ·{" "}
              {g.region_id ? (regionName.get(g.region_id) ?? "Region") : "All regions"}
              {g.kitchen_id ? ` · ${kitchenName.get(g.kitchen_id) ?? "Kitchen"}` : ""}
              <span className="block text-xs text-text-muted">Since {formatDateTime(g.granted_at)}</span>
            </span>
            {self ? null : (
              <ReasonAction
                label="Remove role"
                prompt={`Why are you removing this role from ${person.name}?`}
                confirmLabel="Remove role"
                onConfirm={(reason) => remove.mutateAsync({ assignmentId: g.assignment_id, reason })}
              />
            )}
          </li>
        ))}
      </ul>
    </li>
  );
}

function AddStaff() {
  const canManageRm = useCan("management.regional_managers.manage");
  const regions = useRegions();
  const kitchens = useKitchens();
  const add = useAddStaff();
  const id = useId();
  const roles: Role[] = [
    "KITCHEN_STAFF",
    "KITCHEN_MANAGER",
    "DELIVERY_AGENT",
    ...(canManageRm ? (["REGIONAL_MANAGER"] as Role[]) : []),
  ];
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [role, setRole] = useState<Role>("KITCHEN_STAFF");
  const [region, setRegion] = useState("");
  const [kitchen, setKitchen] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const regionId = region || regions.data?.[0]?.id || "";
  const regionKitchens = (kitchens.data ?? []).filter((k) => k.region_id === regionId);
  const needsKitchen = KITCHEN_ROLES.includes(role);
  const kitchenId = needsKitchen ? kitchen || regionKitchens[0]?.id || "" : "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setDone(null);
    if (!name.trim() || !mobile.trim() || reason.trim().length < 3) {
      setError("Enter a name, a mobile number and a reason of at least 3 characters.");
      return;
    }
    if (needsKitchen && !kitchenId) {
      setError("Kitchen roles need a kitchen in the chosen region.");
      return;
    }
    setError(null);
    try {
      const created = await add.mutateAsync({
        display_name: name.trim(),
        mobile: mobile.trim(),
        role,
        region_id: regionId,
        kitchen_id: needsKitchen ? kitchenId : null,
        reason: reason.trim(),
      });
      setDone(`${created.display_name} added as ${ROLE_LABEL[role]}.`);
      setName("");
      setMobile("");
      setReason("");
    } catch (e) {
      setError(actionError(e));
    }
  }

  return (
    <section aria-labelledby={`${id}-title`} className="rounded-panel border border-border bg-surface p-4">
      <h2 id={`${id}-title`} className="text-lg font-semibold">
        Add staff role
      </h2>
      <form onSubmit={submit} noValidate className="mt-2 grid gap-3 sm:grid-cols-2">
        <Field id={`${id}-name`} label="Name">
          <input
            id={`${id}-name`}
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            className={`mt-1 w-full ${INPUT}`}
            autoComplete="off"
          />
        </Field>
        <Field id={`${id}-mobile`} label="Mobile number">
          <input
            id={`${id}-mobile`}
            value={mobile}
            inputMode="tel"
            maxLength={20}
            onChange={(e) => setMobile(e.target.value)}
            className={`mt-1 w-full ${INPUT}`}
            autoComplete="off"
          />
        </Field>
        <Field id={`${id}-role`} label="Role">
          <select
            id={`${id}-role`}
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className={`mt-1 w-full ${INPUT}`}
          >
            {roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${id}-region`} label="Region">
          <select
            id={`${id}-region`}
            value={regionId}
            onChange={(e) => {
              setRegion(e.target.value);
              setKitchen("");
            }}
            className={`mt-1 w-full ${INPUT}`}
          >
            {(regions.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </Field>
        {needsKitchen ? (
          <Field id={`${id}-kitchen`} label="Kitchen">
            <select
              id={`${id}-kitchen`}
              value={kitchenId}
              onChange={(e) => setKitchen(e.target.value)}
              className={`mt-1 w-full ${INPUT}`}
            >
              {regionKitchens.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
          </Field>
        ) : null}
        <Field id={`${id}-reason`} label="Reason">
          <input
            id={`${id}-reason`}
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
            className={`mt-1 w-full ${INPUT}`}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={add.isPending}>
            Add role
          </Button>
        </div>
      </form>
      {error ? (
        <p role="alert" className="mt-2 text-sm">
          {error}
        </p>
      ) : null}
      {done ? (
        <p role="status" className="mt-2 text-sm">
          {done}
        </p>
      ) : null}
    </section>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}
