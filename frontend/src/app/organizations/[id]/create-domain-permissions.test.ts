import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), "src/app/organizations/[id]", path), "utf-8");
}

describe("organization domain create permission decoupling", () => {
  it("OPO uses useCan(opo.view)", () => {
    expect(source("opo/new/page.tsx")).toContain('useCan("opo.view")');
  });
  it("OPO uses useCan(organizations.view)", () => {
    expect(source("opo/new/page.tsx")).toContain('useCan("organizations.view")');
  });
  it("OPO owner defaults to current organization", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toContain("useState(organizationId)");
    expect(s).toContain("owner_organization_id: ownerOrganizationId");
  });
  it("OPO operator defaults to current organization", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toContain("useState(organizationId)");
    expect(s).toContain("operating_organization_id: operatingOrganizationId");
  });
  it("OPO organizations lookup is gated on organizations.view", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toMatch(/if\s*\(\s*!canViewOrganizations\s*\)\s*return\s*;[\s\S]*?getOrganizations/);
  });
  it("OPO reference lookups are gated on opo.view", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toMatch(/if\s*\(\s*!canViewOpo\s*\)\s*return\s*;[\s\S]*?getHazardSigns/);
    expect(s).toMatch(/if\s*\(\s*!canViewOpo\s*\)\s*return\s*;[\s\S]*?getActivityTypes/);
  });
  it("OPO optional lookups do not block submit", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toContain('<Button type="submit" disabled={pending}>');
    expect(s).not.toContain("supportingLoading");
    expect(s).not.toContain("supportingError");
  });
  it("OPO registration_number maxLength is 100", () => {
    const s = source("opo/new/page.tsx");
    expect(s).toContain("maxLength={100}");
    expect(s).not.toContain("maxLength={128}");
  });
  it("OPO falls back to current organization when no org list is available", () => {
    expect(source("opo/new/page.tsx")).toContain("Текущая организация");
  });

  it("Technical Device uses useCan(opo.view)", () => {
    expect(source("devices/new/page.tsx")).toContain('useCan("opo.view")');
  });
  it("Technical Device OPO lookup is conditional", () => {
    const s = source("devices/new/page.tsx");
    expect(s).toMatch(/if\s*\(\s*!canViewOpo\s*\)\s*return\s*;[\s\S]*?getOpoList/);
  });
  it("Technical Device always offers Без ОПО", () => {
    expect(source("devices/new/page.tsx")).toContain('<SelectItem value={NO_OPO_ID}>Без ОПО</SelectItem>');
  });
  it("Technical Device lookup error does not block submit", () => {
    const s = source("devices/new/page.tsx");
    expect(s).toContain('<Button type="submit" disabled={pending}>');
    expect(s).not.toContain("loadError");
  });
  it("Technical Device serial_number maxLength is 100", () => {
    const s = source("devices/new/page.tsx");
    expect(s).toContain("maxLength={100}");
    expect(s).not.toContain("maxLength={128}");
  });
  it("Technical Device submits a null opo_id for the current organization", () => {
    const s = source("devices/new/page.tsx");
    expect(s).toContain("opo_id: opoId === NO_OPO_ID ? null : opoId");
    expect(s).toContain("organization_id: organizationId");
  });

  it("Building uses useCan(opo.view)", () => {
    expect(source("buildings/new/page.tsx")).toContain('useCan("opo.view")');
  });
  it("Building OPO lookup is conditional", () => {
    const s = source("buildings/new/page.tsx");
    expect(s).toMatch(/if\s*\(\s*!canViewOpo\s*\)\s*return\s*;[\s\S]*?getOpoList/);
  });
  it("Building always offers Без ОПО", () => {
    expect(source("buildings/new/page.tsx")).toContain('<SelectItem value={NO_OPO_ID}>Без ОПО</SelectItem>');
  });
  it("Building lookup error does not block submit", () => {
    const s = source("buildings/new/page.tsx");
    expect(s).toContain('<Button type="submit" disabled={pending}>');
    expect(s).not.toContain("loadError");
  });
  it("Building submits a null opo_id for the current organization", () => {
    const s = source("buildings/new/page.tsx");
    expect(s).toContain("opo_id: opoId === NO_OPO_ID ? null : opoId");
    expect(s).toContain("organization_id: organizationId");
  });
});