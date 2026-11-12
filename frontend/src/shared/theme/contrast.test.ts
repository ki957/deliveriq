// @vitest-environment node
// Every text/background pair in tokens.css meets WCAG 2.2 AA (4.5:1 text, 3:1 focus ring).
// Automated contrast checks do not prove full accessibility; manual review is still required (DDR-23).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const css = readFileSync(fileURLToPath(new URL("./tokens.css", import.meta.url)), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`missing ${selector}`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string): number {
  const [r = 0, g = 0, b = 0] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function token(tokens: Record<string, string>, name: string): string {
  const value = tokens[name];
  if (!value) throw new Error(`token --${name} is missing`);
  return value;
}

function contrast(a: string, b: string): number {
  const [hi = 0, lo = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT_PAIRS: [string, string][] = [
  ["primary-foreground", "primary"],
  ["secondary-foreground", "secondary"],
  ["accent-foreground", "accent"],
  ["text", "background"],
  ["text", "surface"],
  ["text-muted", "background"],
  ["text-muted", "surface"],
  ["nav-foreground", "nav"],
  ["nav-active-foreground", "nav-active"],
];

describe.each(["customer", "kitchen", "delivery", "management", "none"])("%s theme", (portal) => {
  const tokens = block(`[data-portal="${portal}"]`);

  it.each(TEXT_PAIRS)("%s on %s is at least 4.5:1", (fg, bg) => {
    expect(contrast(token(tokens, fg), token(tokens, bg))).toBeGreaterThanOrEqual(4.5);
  });

  it("focus ring is at least 3:1 against the page and the navigation", () => {
    expect(contrast(token(tokens, "focus-ring"), token(tokens, "background"))).toBeGreaterThanOrEqual(3);
    expect(contrast(token(tokens, "nav-foreground"), token(tokens, "nav"))).toBeGreaterThanOrEqual(3);
  });
});

describe("status colours (DDR-100)", () => {
  const root = block(":root");
  it.each(["status-info", "status-success", "status-warning", "status-danger", "status-neutral"])(
    "%s carries white text at >= 4.5:1",
    (name) => {
      expect(contrast(token(root, "status-foreground"), token(root, name))).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("uses the approved values", () => {
    expect(root).toMatchObject({
      "status-info": "#1d4ed8",
      "status-success": "#15803d",
      "status-warning": "#b45309",
      "status-danger": "#b91c1c",
      "status-neutral": "#4b5563",
    });
  });
});
