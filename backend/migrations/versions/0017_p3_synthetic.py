"""P3 manifests, synthetic flags, GPS and narrow read/publish functions (DDR-118).

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE TABLE synthetic.manifests (
    profile text PRIMARY KEY CHECK (profile IN ('demo', 'ml')),
    generator_seed bigint NOT NULL,
    generator_version integer NOT NULL CHECK (generator_version = 1),
    date_from date NOT NULL,
    date_to date NOT NULL CHECK (date_to >= date_from),
    region_id uuid NOT NULL,
    kitchen_id uuid NOT NULL,
    reference_data jsonb NOT NULL,
    content_sha256 text,
    generated_at timestamptz,
    build_status text NOT NULL DEFAULT 'building' CHECK (build_status IN ('building', 'ready', 'failed')),
    pipeline_run_id uuid REFERENCES ops.pipeline_runs(id),
    is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic)
);
ALTER TABLE synthetic.events
    ADD COLUMN profile text NOT NULL DEFAULT 'demo' REFERENCES synthetic.manifests(profile),
    ADD COLUMN is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    ADD COLUMN is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic);
CREATE INDEX synthetic_events_profile_idx ON synthetic.events(profile);
ALTER TABLE synthetic.events ADD COLUMN landed_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE synthetic.gps_tracks (
    order_id uuid PRIMARY KEY,
    profile text NOT NULL REFERENCES synthetic.manifests(profile),
    region_id uuid NOT NULL,
    kitchen_id uuid NOT NULL,
    rider_key text NOT NULL,
    is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic)
);
CREATE TABLE synthetic.gps_points (
    order_id uuid NOT NULL REFERENCES synthetic.gps_tracks(order_id),
    sequence integer NOT NULL CHECK (sequence BETWEEN 0 AND 60),
    occurred_at timestamptz NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    PRIMARY KEY (order_id, sequence)
);
-- Flags are derived by the database, never supplied by the API or generator.
CREATE FUNCTION synthetic.mark_fixture() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN NEW.is_test_fixture := true; NEW.is_synthetic := true; RETURN NEW; END $$;
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['manifests', 'events', 'gps_tracks', 'gps_points'] LOOP
        EXECUTE format('CREATE TRIGGER synthetic_fixture BEFORE INSERT OR UPDATE ON synthetic.%I '
                       'FOR EACH ROW EXECUTE FUNCTION synthetic.mark_fixture()', t);
    END LOOP;
END $$;

REVOKE SELECT ON app.menu_items FROM p3_synth;
GRANT SELECT (id, kitchen_id, category_id, name, price_paise, publication_status, is_test_fixture)
    ON app.menu_items TO p3_synth;
GRANT SELECT (id, code, name, status) ON app.regions TO p3_synth;
GRANT SELECT (id, code, region_id, name, status) ON app.kitchens TO p3_synth;
GRANT SELECT (id, name) ON app.menu_categories TO p3_synth;
GRANT SELECT (id, name, unit, origin) ON app.ingredients TO p3_synth;
-- Config reads go through a fixed-key view: no unrelated settings or secrets.
CREATE VIEW synthetic.pricing_inputs AS
SELECT key, value, scope_type, region_id, kitchen_id FROM app.config_settings
WHERE key IN ('MINIMUM_FOOD_SUBTOTAL', 'DELIVERY_FEE_FLAT');
GRANT SELECT ON synthetic.pricing_inputs TO p3_synth;
GRANT SELECT, INSERT ON synthetic.manifests, synthetic.gps_tracks, synthetic.gps_points TO p3_synth;
GRANT UPDATE (content_sha256, generated_at, build_status, pipeline_run_id) ON synthetic.manifests TO p3_synth;

CREATE FUNCTION ops.synthetic_fixture_counts() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT jsonb_build_object(
    'synthetic.manifests', (SELECT count(*) FROM synthetic.manifests),
    'synthetic.events', (SELECT count(*) FROM synthetic.events),
    'synthetic.gps_tracks', (SELECT count(*) FROM synthetic.gps_tracks),
    'synthetic.gps_points', (SELECT count(*) FROM synthetic.gps_points))
$$;
REVOKE ALL ON FUNCTION ops.synthetic_fixture_counts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.synthetic_fixture_counts() TO app_api;

CREATE FUNCTION ops.synthetic_status() RETURNS TABLE (
    profile text, generator_seed bigint, generator_version integer, date_from date, date_to date,
    region_id uuid, kitchen_id uuid, content_sha256 text, generated_at timestamptz,
    build_status text, pipeline_run_id uuid
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT profile, generator_seed, generator_version, date_from, date_to, region_id, kitchen_id,
       content_sha256, generated_at, build_status, pipeline_run_id FROM synthetic.manifests
$$;
REVOKE ALL ON FUNCTION ops.synthetic_status() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.synthetic_status() TO app_api;

CREATE FUNCTION ops.synthetic_track(track_id uuid) RETURNS TABLE (
    order_id uuid, region_id uuid, kitchen_id uuid, rider_key text,
    sequence integer, occurred_at timestamptz, latitude double precision, longitude double precision
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT t.order_id, t.region_id, t.kitchen_id, t.rider_key, p.sequence, p.occurred_at, p.latitude, p.longitude
FROM synthetic.gps_tracks t JOIN synthetic.gps_points p USING (order_id)
WHERE t.profile = 'demo' AND t.order_id = track_id ORDER BY p.sequence
$$;
REVOKE ALL ON FUNCTION ops.synthetic_track(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.synthetic_track(uuid) TO app_api;

CREATE FUNCTION ops.synthetic_tracks() RETURNS TABLE (order_id uuid, region_id uuid, kitchen_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT order_id, region_id, kitchen_id FROM synthetic.gps_tracks WHERE profile = 'demo' ORDER BY order_id
$$;
REVOKE ALL ON FUNCTION ops.synthetic_tracks() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.synthetic_tracks() TO app_api;

CREATE FUNCTION ops.publish_synthetic_freshness(run_id uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ops.pipeline_runs r JOIN synthetic.manifests m
                   ON m.pipeline_run_id = r.id WHERE r.id = run_id AND r.pipeline = 'p3_synthetic'
                   AND m.profile = 'demo' AND m.build_status = 'ready') THEN
        RAISE EXCEPTION 'no validated demo manifest for this P3 run';
    END IF;
    INSERT INTO ops.dataset_freshness (dataset, fresh_as_of, run_id)
    VALUES ('analytics_synthetic', now(), run_id)
    ON CONFLICT (dataset) DO UPDATE SET fresh_as_of = now(), run_id = EXCLUDED.run_id, updated_at = now();
END $$;
REVOKE ALL ON FUNCTION ops.publish_synthetic_freshness(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.publish_synthetic_freshness(uuid) TO p3_synth;

CREATE FUNCTION ops.invalidate_synthetic_freshness() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
DELETE FROM ops.dataset_freshness WHERE dataset = 'analytics_synthetic'
$$;
REVOKE ALL ON FUNCTION ops.invalidate_synthetic_freshness() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.invalidate_synthetic_freshness() TO p3_synth;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION ops.invalidate_synthetic_freshness();
    DROP FUNCTION ops.publish_synthetic_freshness(uuid);
    DROP FUNCTION ops.synthetic_tracks();
    DROP FUNCTION ops.synthetic_track(uuid);
    DROP FUNCTION ops.synthetic_status();
    DROP FUNCTION ops.synthetic_fixture_counts();
    DROP VIEW synthetic.pricing_inputs;
    DROP TABLE synthetic.gps_points, synthetic.gps_tracks;
    ALTER TABLE synthetic.events DROP COLUMN profile, DROP COLUMN is_synthetic, DROP COLUMN is_test_fixture, DROP COLUMN landed_at;
    DROP TABLE synthetic.manifests;
    DROP FUNCTION synthetic.mark_fixture();
    REVOKE SELECT (id, code, name, status) ON app.regions FROM p3_synth;
    REVOKE SELECT (id, code, region_id, name, status) ON app.kitchens FROM p3_synth;
    REVOKE SELECT (id, name) ON app.menu_categories FROM p3_synth;
    REVOKE SELECT (id, name, unit, origin) ON app.ingredients FROM p3_synth;
    REVOKE SELECT (id, kitchen_id, category_id, name, price_paise, publication_status, is_test_fixture)
        ON app.menu_items FROM p3_synth;
    GRANT SELECT ON app.menu_items TO p3_synth;
    """)
