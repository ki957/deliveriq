#!/usr/bin/env bash
# Runs inside the e2e container (`make e2e`). Works on copies in /tmp so the host checkout and its
# node_modules are never modified; only screenshots and failure artefacts are written back.
set -euo pipefail

export HOME=/tmp/home
mkdir -p "$HOME" /tmp/app /tmp/e2e

restore_ownership() {
  chown -R "${HOST_UID:-1000}:${HOST_GID:-1000}" /work/tests/e2e/__screenshots__ /work/tests/e2e/test-results 2>/dev/null || true
}

tar -C /work/frontend --exclude=node_modules --exclude=dist -cf - . | tar -C /tmp/app -xf -
tar -C /work/tests/e2e --exclude=node_modules --exclude=test-results --exclude=__screenshots__ -cf - . | tar -C /tmp/e2e -xf -

cd /tmp/app
npm ci --no-audit --no-fund --loglevel=error
npx vite build --outDir /tmp/dist --emptyOutDir --logLevel warn
npx vite preview --outDir /tmp/dist --host 127.0.0.1 --port 4173 --strictPort >/tmp/preview.log 2>&1 &
preview=$!
trap 'kill "$preview" 2>/dev/null || true; restore_ownership' EXIT

cd /tmp/e2e
npm ci --no-audit --no-fund --loglevel=error
node -e '
const deadline = Date.now() + 60_000;
(async function wait() {
  try { if ((await fetch("http://127.0.0.1:4173/")).ok) return; } catch {}
  if (Date.now() > deadline) { console.error("preview server did not start"); process.exit(1); }
  setTimeout(wait, 500);
})();'

mkdir -p /work/tests/e2e/__screenshots__ /work/tests/e2e/test-results
E2E_SNAPSHOT_DIR=/work/tests/e2e/__screenshots__ E2E_OUTPUT_DIR=/work/tests/e2e/test-results \
  npx playwright test ${PLAYWRIGHT_ARGS:-}
