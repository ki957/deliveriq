import { useState } from "react";

import {
  useApproveCustomerGoldenSet,
  useCustomerGoldenSet,
  useCustomerKnowledgeVersions,
  useDecideCustomerKnowledge,
} from "./knowledge-api";

export function CustomerKnowledgePage() {
  const versions = useCustomerKnowledgeVersions(true);
  const golden = useCustomerGoldenSet(true);
  const decide = useDecideCustomerKnowledge();
  const approveGolden = useApproveCustomerGoldenSet();
  const [reason, setReason] = useState("");
  return (
    <main aria-labelledby="customer-knowledge-title">
      <h1 id="customer-knowledge-title">Customer Assistant knowledge</h1>
      <p>
        Draft source content and the Customer golden set require Customer Assistant approval before
        publication.
      </p>
      <label>
        Decision reason <input value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
      {versions.isPending && <p>Loading drafts…</p>}
      {versions.isError && <p role="alert">Unable to load Customer drafts.</p>}
      <ul>
        {versions.data?.map((version) => (
          <li key={version.id}>
            <span>
              {version.display_name} — {version.status}
            </span>
            {version.status === "DRAFT" && (
              <>
                <button
                  type="button"
                  onClick={() => decide.mutate({ versionId: version.id, approve: true, reason })}
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => decide.mutate({ versionId: version.id, approve: false, reason })}
                >
                  Reject
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      {golden.data && (
        <section aria-labelledby="customer-golden-title">
          <h2 id="customer-golden-title">Customer golden set</h2>
          <p>
            {golden.data.approval_label} — {golden.data.case_count} cases, {golden.data.leak_count} leaks.
          </p>
          {golden.data.status === "DRAFT" && (
            <button type="button" onClick={() => approveGolden.mutate({ setId: golden.data.id, reason })}>
              Approve golden set
            </button>
          )}
        </section>
      )}
    </main>
  );
}
