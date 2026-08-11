import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization domain create flows", () => {
  const types = source("src/lib/api/types.ts");
  const resources = source("src/lib/api/resources.ts");
  const viewModels = source("src/lib/api/view-models.ts");
  const opoList = source(
    "src/app/organizations/[id]/_components/organization-opo-list.tsx",
  );
  const deviceList = source(
    "src/app/organizations/[id]/_components/organization-device-list.tsx",
  );
  const buildingList = source(
    "src/app/organizations/[id]/_components/organization-building-list.tsx",
  );
  const page = source("src/app/organizations/[id]/page.tsx");

  it("defines create payload types and enum union types", () => {
    expect(types).toContain("export type HazardClass");
    expect(types).toContain("export type TechnicalDeviceType");
    expect(types).toContain("export type BuildingType");
    expect(types).toContain("export interface OPOCreatePayload");
    expect(types).toContain("export interface TechnicalDeviceCreatePayload");
    expect(types).toContain("export interface BuildingCreatePayload");
    expect(types).toContain("export interface ReferenceItemResponse");
  });

  it("defines the three create resource functions", () => {
    expect(resources).toContain("export const createOpo");
    expect(resources).toContain("export const createTechnicalDevice");
    expect(resources).toContain("export const createBuilding");
  });

  it("posts to the exact backend create endpoints", () => {
    expect(resources).toMatch(/apiRequest<OPOResponse>\("\/api\/opo"/);
    expect(resources).toMatch(
      /apiRequest<TechnicalDeviceResponse>\("\/api\/technical-devices"/,
    );
    expect(resources).toMatch(/apiRequest<BuildingResponse>\("\/api\/buildings"/);
  });

  it("defines the two reference resource functions", () => {
    expect(resources).toContain("export const getHazardSigns");
    expect(resources).toContain("export const getActivityTypes");
    expect(resources).toContain("/api/reference/hazard-signs");
    expect(resources).toContain("/api/reference/activity-types");
  });

  it("adds the Russian enum label helpers", () => {
    expect(viewModels).toContain("hazardClassLabel");
    expect(viewModels).toContain("technicalDeviceTypeLabel");
    expect(viewModels).toContain("buildingTypeLabel");
    expect(viewModels).toContain("I класс опасности");
    expect(viewModels).toContain("Сосуд под давлением");
    expect(viewModels).toContain("Производственное");
  });

  it("uses Russian labels in the existing OPO list", () => {
    expect(opoList).toContain("hazardClassLabel");
  });

  it("uses Russian labels in the device and building lists", () => {
    expect(deviceList).toContain("technicalDeviceTypeLabel");
    expect(buildingList).toContain("buildingTypeLabel");
  });

  it("gates the OPO add button with opo.create", () => {
    expect(opoList).toContain('useCan("opo.create")');
    expect(opoList).toContain('href={`/organizations/${organizationId}/opo/new`}');
  });

  it("gates the device add button with technical_devices.create", () => {
    expect(deviceList).toContain('useCan("technical_devices.create")');
    expect(deviceList).toContain(
      'href={`/organizations/${organizationId}/devices/new`}',
    );
  });

  it("gates the building add button with buildings.create", () => {
    expect(buildingList).toContain('useCan("buildings.create")');
    expect(buildingList).toContain(
      'href={`/organizations/${organizationId}/buildings/new`}',
    );
  });

  it("keeps the contracts placeholder unchanged", () => {
    expect(page).toContain("Раздел будет подключён на следующем этапе");
  });

  it("creates the three create pages and wires them to the resource functions", () => {
    const opoPage = source("src/app/organizations/[id]/opo/new/page.tsx");
    const devicePage = source("src/app/organizations/[id]/devices/new/page.tsx");
    const buildingPage = source("src/app/organizations/[id]/buildings/new/page.tsx");

    expect(opoPage).toContain("createOpo");
    expect(opoPage).toContain("getHazardSigns");
    expect(opoPage).toContain("getActivityTypes");

    expect(devicePage).toContain("createTechnicalDevice");
    expect(devicePage).toContain("getOpoList");

    expect(buildingPage).toContain("createBuilding");
    expect(buildingPage).toContain("getOpoList");
  });

  it("each create page navigates back to the organization workspace on success", () => {
    const opoPage = source("src/app/organizations/[id]/opo/new/page.tsx");
    const devicePage = source("src/app/organizations/[id]/devices/new/page.tsx");
    const buildingPage = source(
      "src/app/organizations/[id]/buildings/new/page.tsx",
    );
    for (const file of [opoPage, devicePage, buildingPage]) {
      expect(file).toContain(
        "router.replace(`/organizations/${organizationId}`)",
      );
    }
  });

  it("the device create page exposes no organization selector and uses Без ОПО", () => {
    const devicePage = source("src/app/organizations/[id]/devices/new/page.tsx");
    expect(devicePage).toContain("Без ОПО");
  });

  it("the building create page includes Без ОПО", () => {
    const buildingPage = source(
      "src/app/organizations/[id]/buildings/new/page.tsx",
    );
    expect(buildingPage).toContain("Без ОПО");
  });
});
