import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization domain tabs", () => {
  const page = source("src/app/organizations/[id]/page.tsx");
  const resources = source("src/lib/api/resources.ts");
  const types = source("src/lib/api/types.ts");

  it("defines the OPO, technical device, and building API response types", () => {
    for (const type of [
      "OPOResponse",
      "OPOPaginatedResponse",
      "TechnicalDeviceResponse",
      "TechnicalDevicePaginatedResponse",
      "BuildingResponse",
      "BuildingPaginatedResponse",
    ]) {
      expect(types).toContain(`export interface ${type}`);
    }
  });

  it("defines typed resource functions for the three domain lists", () => {
    expect(resources).toContain("export const getOpoList");
    expect(resources).toContain("export const getTechnicalDevices");
    expect(resources).toContain("export const getBuildings");
  });

  it("hits the existing backend list endpoints", () => {
    expect(resources).toContain("/api/opo?");
    expect(resources).toContain("/api/technical-devices?");
    expect(resources).toContain("/api/buildings?");
  });

  it("sends organization_id in all three resource functions", () => {
    const setOrganizationId = resources.split(
      'searchParams.set("organization_id", params.organization_id);',
    ).length - 1;
    expect(setOrganizationId).toBe(3);
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
    expect(page).toContain('["contracts"].map((tab)');
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
      const file = source(
        `src/app/organizations/[id]/_components/${component}.tsx`,
      );
      expect(file).toContain('"use client"');
      expect(file).toContain("organizationId: string");
      expect(file).toContain("AbortController");
      expect(file).toContain("page_size: 100");
    }
  });

  it("keeps the required empty-state copy in each component", () => {
    const opo = source(
      "src/app/organizations/[id]/_components/organization-opo-list.tsx",
    );
    const devices = source(
      "src/app/organizations/[id]/_components/organization-device-list.tsx",
    );
    const buildings = source(
      "src/app/organizations/[id]/_components/organization-building-list.tsx",
    );
    expect(opo).toContain("ОПО для этой организации пока не добавлены.");
    expect(devices).toContain(
      "Технические устройства для этой организации пока не добавлены.",
    );
    expect(buildings).toContain(
      "Здания и сооружения для этой организации пока не добавлены.",
    );
  });
});
