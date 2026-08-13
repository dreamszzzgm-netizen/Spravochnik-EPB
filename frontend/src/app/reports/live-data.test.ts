import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("management reports live data", () => {
  it("loads management KPI from backend instead of mock data", () => {
    const page = source("src/app/reports/page.tsx");
    const resources = source("src/lib/api/resources.ts");

    expect(resources).toContain("getManagementReport");
    expect(resources).toContain('"/api/reports/management"');
    expect(page).toContain("getManagementReport");
    expect(page).toContain("organizations_total");
    expect(page).toContain("contracts.active");
    expect(page).toContain("tasks.overdue");
    expect(page).not.toContain("mockManagement");
  });
});
