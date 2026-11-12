// DDR-81: fail if the committed TypeScript client differs from what backend/openapi.json generates.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const committed = "src/shared/api/generated/schema.d.ts";
const dir = mkdtempSync(join(tmpdir(), "diq-api-"));
const fresh = join(dir, "schema.d.ts");
try {
  execFileSync("npx", ["openapi-typescript", "../backend/openapi.json", "-o", fresh], { stdio: "ignore" });
  if (readFileSync(fresh, "utf8") !== readFileSync(committed, "utf8")) {
    console.error(`API client is out of date: run "npm run api:generate" and commit ${committed}`);
    process.exit(1);
  }
  console.log("API client is up to date");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
