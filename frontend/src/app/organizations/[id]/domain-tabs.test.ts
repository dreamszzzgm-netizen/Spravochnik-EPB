import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

const pagePath = "src/app/organizations/[id]/page.tsx";
const page = source(pagePath);

describe("organization domain tabs", () => {
  it("keeps the domain tabs visible in the organization workspace", () => {
    for (const tab of ["opo", "devices", "buildings", "contracts"]) {
      expect(page).toContain(`value="${tab}"`);
    }
  });

  it("imports the three domain list components", () => {
    expect(page).toContain(
      'import { OrganizationOpoList } from "./_components/organization-opo-list";',
    );
    expect(page).toContain(
      'import { OrganizationDeviceList } from "./_components/organization-device-list";',
    );
    expect(page).toContain(
      'import { OrganizationBuildingList } from "./_components/organization-building-list";',
    );
  });

  it("renders each domain list with organizationId={id}", () => {
    expect(page).toContain("<OrganizationOpoList organizationId={id} />");
    expect(page).toContain("<OrganizationDeviceList organizationId={id} />");
    expect(page).toContain("<OrganizationBuildingList organizationId={id} />");
  });

  it("no longer uses the shared placeholder loop for opo, devices, or buildings", () => {
    expect(page).not.toContain('["opo", "devices", "buildings", "contracts"]');
    expect(page).toContain('value="contracts"');
    expect(page).not.toContain('value="opo" className="mt-4">\n            <Card>');
    expect(page).not.toContain('value="devices" className="mt-4">\n            <Card>');
    expect(page).not.toContain('value="buildings" className="mt-4">\n            <Card>');
  });

  it("keeps the contracts placeholder", () => {
    expect(page).toContain('value="contracts"');
    expect(page).toContain("Раздел будет подключён на следующем этапе");
  });

  it("creates client components that fetch their own resource", () => {
    for (const component of [
      "organization-opo-list",
      "organization-device-list",
      "organization-building-list",
    ]) {
      const path = `src/app/organizations/[id]/_components/${component}.tsx`;
      expect(existsSync(resolve(process.cwd(), path))).toBe(true);
      const content = source(path);
      expect(content).toContain('"use client"');
    }
  });
});
