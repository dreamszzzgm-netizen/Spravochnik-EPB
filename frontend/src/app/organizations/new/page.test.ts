import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("new organization smart import", () => {
  const page = source("src/app/organizations/new/page.tsx");

  it("shows IP-only identifiers without KPP or OGRN", () => {
    expect(page).toContain('["inn", "ogrnip"]');
    expect(page).toContain('["inn", "kpp", "ogrn"]');
  });

  it("has IP-specific residence and passport fields", () => {
    expect(page).toContain("Место жительства");
    expect(page).toContain("Паспортные данные");
    expect(page).toContain("residence_address");
    expect(page).toContain("passport_details");
  });

  it("requires explicit apply after preview", () => {
    expect(page).toContain("previewOrganizationImport");
    expect(page).toContain("Применить к форме");
    expect(page).toContain("setImportPreview");
  });

  it("does not submit legal entity fields for IP", () => {
    expect(page).toContain("legal_address: isIp ? null");
    expect(page).toContain("director_name: isIp ? null");
    expect(page).toContain("passport_details: isIp ? passportDetails.trim() || null : null");
  });
});
