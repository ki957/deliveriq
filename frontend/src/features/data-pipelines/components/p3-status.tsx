import { lazy, Suspense, useState } from "react";
import { Link } from "react-router";

import { useP3Status, useP3Track, useP3Tracks } from "../api";
import { useCan } from "@/shared/auth/require-permission";
import { formatDateTime } from "@/shared/utils/format";

const P3Map = lazy(async () => ({ default: (await import("./p3-map")).P3Map }));

export function P3StatusPanel() {
  const canOperate = useCan("pipelines.operate");
  const statuses = useP3Status(true);
  const tracks = useP3Tracks(true);
  const [selected, setSelected] = useState("");
  const track = useP3Track(selected);
  const demo = statuses.data?.find((s) => s.profile === "demo");
  return (
    <section
      className="mt-4 space-y-3 rounded-panel border border-border bg-surface p-4"
      aria-label="P3 simulated data"
    >
      <h2 className="text-lg font-semibold">Simulated data</h2>
      <p className="text-sm">
        Generated from TEST dishes with labelled test defaults. This is not live order history.
      </p>
      {statuses.isLoading ? <p role="status">Loading P3 status…</p> : null}
      {statuses.isError || tracks.isError ? <p role="alert">Could not load simulated data.</p> : null}
      {demo ? (
        <p className="text-sm">
          Demo: {demo.date_from} to {demo.date_to} · {demo.build_status} · seed {demo.generator_seed} ·
          generated {formatDateTime(demo.generated_at)}
        </p>
      ) : (
        <p className="text-sm">No demo set generated yet.</p>
      )}
      {statuses.data?.some((s) => s.profile === "ml") ? (
        <p className="text-sm">Offline ML set: generated once for training, separate from demo reports.</p>
      ) : null}
      {demo?.build_status === "ready" ? (
        <Link className="underline" to="/management/reports">
          View Simulated reports
        </Link>
      ) : null}
      {canOperate ? (
        <p className="text-xs text-text-muted">The offline ML set is generated explicitly from the CLI.</p>
      ) : null}
      {tracks.data?.length ? (
        <div>
          <label htmlFor="p3-track" className="block text-sm font-medium">
            Simulated GPS track
          </label>
          <select
            id="p3-track"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
          >
            <option value="">Choose a track</option>
            {tracks.data.map((item, index) => (
              <option key={item.order_id} value={item.order_id}>
                Track {index + 1}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p className="text-sm">No synthetic GPS tracks in your region.</p>
      )}
      {track.isLoading ? <p role="status">Loading simulated GPS track…</p> : null}
      {track.data ? (
        <Suspense fallback={<p>Loading map…</p>}>
          <P3Map points={track.data} />
        </Suspense>
      ) : null}
    </section>
  );
}
