import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization smart import hardening", () => {
  const newPage = source("src/app/organizations/new/page.tsx");
  const editPage = source("src/app/organizations/[id]/edit/page.tsx");
  const resources = source("src/lib/api/resources.ts");

  it("shows legal-form-specific identifiers on create and edit", () => {
    for (const page of [newPage, editPage]) {
      expect(page).toContain('["inn", "ogrnip"]');
      expect(page).toContain('["inn", "kpp", "ogrn"]');
    }
  });

  it("has IP-specific residence and passport fields on create and edit", () => {
    for (const page of [newPage, editPage]) {
      expect(page).toContain("Место жительства");
      expect(page).toContain("Паспортные данные");
      expect(page).toContain("residence_address");
      expect(page).toContain("passport_details");
    }
  });

  it("requires explicit apply after preview", () => {
    expect(newPage).toContain("previewOrganizationImport");
    expect(newPage).toContain("Применить к форме");
    expect(newPage).toContain("setImportPreview");
  });

  it("does not submit legal entity fields for IP", () => {
    for (const page of [newPage, editPage]) {
      expect(page).toContain("legal_address: isIp ? null");
      expect(page).toContain("director_name: isIp ? null");
      expect(page).toContain("passport_details: isIp ? passportDetails.trim() || null : null");
    }
  });

  it("supports file preview without automatic save", () => {
    expect(resources).toContain("previewOrganizationImportFile");
    expect(resources).toContain("FormData");
    expect(newPage).toContain("type=\"file\"");
    expect(newPage).toContain("previewOrganizationImportFile");
    expect(newPage).toContain("Применить к форме");
  });
});
