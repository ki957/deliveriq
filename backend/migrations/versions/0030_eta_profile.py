"""Immutable, PII-free Task 19 ETA simulation profile (DDR-125).

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

UPGRADE_SQL = """
CREATE TABLE synthetic.eta_profiles (
    profile text PRIMARY KEY CHECK (profile = 'ml_eta_v2'),
    generator_seed bigint NOT NULL CHECK (generator_seed = 56),
    generator_version integer NOT NULL CHECK (generator_version = 2),
    date_from date NOT NULL,
    date_to date NOT NULL CHECK (date_to >= date_from),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    sample_count integer NOT NULL CHECK (sample_count > 0),
    generated_at timestamptz NOT NULL DEFAULT now(),
    build_status text NOT NULL DEFAULT 'building' CHECK (build_status IN ('building', 'ready')),
    is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic)
);
CREATE TABLE synthetic.eta_training_samples (
    profile text NOT NULL REFERENCES synthetic.eta_profiles(profile),
    sample_id uuid NOT NULL,
    sample_day date NOT NULL,
    road_km numeric(7, 3) NOT NULL CHECK (road_km > 0 AND road_km <= 6),
    duration_seconds numeric(9, 2) NOT NULL CHECK (duration_seconds > 0),
    is_test_fixture boolean NOT NULL DEFAULT true CHECK (is_test_fixture),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    PRIMARY KEY (profile, sample_id)
);
CREATE INDEX eta_training_samples_day_idx ON synthetic.eta_training_samples(profile, sample_day);
REVOKE ALL ON synthetic.eta_profiles, synthetic.eta_training_samples FROM PUBLIC;
GRANT SELECT ON synthetic.eta_profiles, synthetic.eta_training_samples TO p3_synth;
GRANT INSERT ON synthetic.eta_profiles, synthetic.eta_training_samples TO p3_synth;
REVOKE UPDATE, DELETE, TRUNCATE ON synthetic.eta_profiles, synthetic.eta_training_samples FROM p3_synth;
CREATE FUNCTION synthetic.guard_eta_sample_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, synthetic AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM synthetic.eta_profiles p
                   WHERE p.profile = NEW.profile AND p.build_status = 'building') THEN
        RAISE EXCEPTION 'ETA samples can only be inserted while the profile is building';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER eta_sample_insert_only_while_building BEFORE INSERT ON synthetic.eta_training_samples
    FOR EACH ROW EXECUTE FUNCTION synthetic.guard_eta_sample_insert();
CREATE FUNCTION synthetic.guard_eta_profile_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.build_status <> 'building' OR NEW.build_status <> 'ready'
       OR (to_jsonb(NEW) - 'build_status') IS DISTINCT FROM (to_jsonb(OLD) - 'build_status') THEN
        RAISE EXCEPTION 'ETA profiles are immutable after publication';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER eta_profile_publish_once BEFORE UPDATE ON synthetic.eta_profiles
    FOR EACH ROW EXECUTE FUNCTION synthetic.guard_eta_profile_update();
CREATE FUNCTION ops.publish_eta_profile(p_profile text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, synthetic AS $$
DECLARE v_manifest synthetic.eta_profiles%ROWTYPE;
BEGIN
    SELECT * INTO v_manifest FROM synthetic.eta_profiles WHERE profile = p_profile FOR UPDATE;
    IF v_manifest.profile IS NULL OR v_manifest.build_status <> 'building'
       OR (SELECT count(*) FROM synthetic.eta_training_samples WHERE profile = p_profile) <> v_manifest.sample_count
       OR (SELECT min(sample_day) FROM synthetic.eta_training_samples WHERE profile = p_profile) <> v_manifest.date_from
       OR (SELECT max(sample_day) FROM synthetic.eta_training_samples WHERE profile = p_profile) <> v_manifest.date_to THEN
        RAISE EXCEPTION 'ETA profile does not match its manifest';
    END IF;
    UPDATE synthetic.eta_profiles SET build_status = 'ready' WHERE profile = p_profile;
END $$;
REVOKE ALL ON FUNCTION ops.publish_eta_profile(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.publish_eta_profile(text) TO p3_synth;
CREATE FUNCTION ops.eta_profile_status() RETURNS TABLE (
    profile text, generator_seed bigint, generator_version integer,
    date_from date, date_to date, content_sha256 text, sample_count integer,
    generated_at timestamptz, build_status text
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT profile, generator_seed, generator_version, date_from, date_to, content_sha256,
       sample_count, generated_at, build_status FROM synthetic.eta_profiles
$$;
CREATE FUNCTION ops.eta_profile_samples() RETURNS TABLE (
    sample_day date, road_km numeric, duration_seconds numeric
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
SELECT s.sample_day, s.road_km, s.duration_seconds
FROM synthetic.eta_training_samples s JOIN synthetic.eta_profiles p USING (profile)
WHERE p.profile = 'ml_eta_v2' AND p.build_status = 'ready' ORDER BY s.sample_day, s.sample_id
$$;
REVOKE ALL ON FUNCTION ops.eta_profile_status(), ops.eta_profile_samples() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.eta_profile_status(), ops.eta_profile_samples() TO app_api;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION ops.eta_profile_samples();
    DROP FUNCTION ops.eta_profile_status();
    DROP FUNCTION ops.publish_eta_profile(text);
    DROP TRIGGER eta_profile_publish_once ON synthetic.eta_profiles;
    DROP TRIGGER eta_sample_insert_only_while_building ON synthetic.eta_training_samples;
    DROP FUNCTION synthetic.guard_eta_profile_update();
    DROP FUNCTION synthetic.guard_eta_sample_insert();
    DROP TABLE synthetic.eta_training_samples, synthetic.eta_profiles;
    """)
