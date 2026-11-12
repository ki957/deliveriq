# PostgreSQL 16 + pgvector 0.8.1 + PostGIS 3 (DOCKER_DEPLOYMENT_DESIGN §4, §17). Base pinned by digest.
# Built on the official pgvector image (Debian bookworm). The postgis/postgis:16-3.5 image was
# rejected: it is based on Debian bullseye, whose PGDG apt repository has been retired.
FROM pgvector/pgvector:0.8.1-pg16-bookworm@sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337

# PostGIS from the PGDG repository already configured in the base image. The server packages are
# upgraded in the same step: PGDG builds PostGIS against the latest 16.x minor release, and a newer
# PostGIS on an older server fails at CREATE EXTENSION (undefined symbol). Minor upgrades keep the
# extension ABI, so the base image's pgvector build is unaffected.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16 postgresql-client-16 postgresql-16-postgis-3 \
    && rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
