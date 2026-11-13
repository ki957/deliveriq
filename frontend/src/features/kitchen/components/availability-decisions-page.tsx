import { useState } from "react";

import { useAvailabilityRequests, useDecideAvailability, type AvailabilityRequest } from "../api";
import { refusalText } from "../format";
import { AvailabilityList } from "./availability-list";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";

// Management → Dish Availability (KI-24; DDR-111 (7)): RM own regions, CA all regions. Audited.
export function AvailabilityDecisionsPage() {
  const requests = useAvailabilityRequests(false);
  const state = queryState(requests, { loading: "Loading requests…" });
  return (
    <section className="max-w-4xl space-y-4">
      <h1 className="text-2xl font-semibold">Dish Availability</h1>
      <p className="text-sm text-text-muted">
        Kitchens ask to take a dish off the customer menu, or to bring it back. Only your approval changes the
        menu.
      </p>
      {state ?? (
        <AvailabilityList
          rows={requests.data ?? []}
          actions={(r) => (r.status === "PENDING" ? <Decide request={r} /> : null)}
        />
      )}
    </section>
  );
}

function Decide({ request }: { request: AvailabilityRequest }) {
  const decide = useDecideAvailability();
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (rejecting) {
    return (
      <ReasonForm
        label={`Why is the request for ${request.dish_name} rejected?`}
        confirmLabel="Reject request"
        onCancel={() => setRejecting(false)}
        onConfirm={async (reason) => {
          try {
            await decide.mutateAsync({ id: request.id, approve: false, reason });
          } catch (e) {
            throw new Error(refusalText(e), { cause: e });
          }
        }}
      />
    );
  }
  return (
    <div className="mt-2">
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={decide.isPending}
          onClick={async () => {
            setError(null);
            try {
              await decide.mutateAsync({ id: request.id, approve: true, reason: null });
            } catch (e) {
              setError(refusalText(e));
            }
          }}
        >
          Approve
        </Button>
        <Button variant="secondary" onClick={() => setRejecting(true)} disabled={decide.isPending}>
          Reject
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}
