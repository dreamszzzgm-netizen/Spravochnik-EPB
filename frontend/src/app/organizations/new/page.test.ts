import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization smart import hardening", () => {
  const proxy = source("src/proxy.ts");
  const newPage = source("src/app/organizations/new/page.hardened.tsx");
  const editPage = source("src/app/organizations/[id]/edit/page.hardened.tsx");
  const fields = source("src/components/organization-form-fields.tsx");
  const model = source("src/components/organization-form-model.ts");
  const smartImport = source("src/components/organization-smart-import.tsx");
  const resources = source("src/lib/api/resources.ts");

  it("activates hardened create and edit flows at the existing URLs", () => {
    expect(proxy).toContain('pathname === "/organizations/new"');
    expect(proxy).toContain('/organizations/new-hardened');
    expect(proxy).toContain('/edit-hardened');
    expect(proxy).toContain('matcher: ["/organizations/new", "/organizations/:id/edit"]');
    expect(newPage).toContain("OrganizationFormFields");
    expect(editPage).toContain("OrganizationFormFields");
  });

  it("shows legal-form-specific identifiers", () => {
    expect(model).toContain('["inn", "ogrnip"]');
    expect(model).toContain('["inn", "kpp", "ogrn"]');
    expect(fields).toContain("identifierTypesFor(values.orgType)");
  });

  it("has IP-specific residence and passport fields", () => {
    expect(fields).toContain("Место жительства");
    expect(fields).toContain("Паспортные данные");
    expect(fields).toContain("residenceAddress");
    expect(fields).toContain("passportDetails");
  });

  it("filters incompatible fields before submit", () => {
    expect(model).toContain("legal_address: isIp ? null");
    expect(model).toContain("actual_address: isIp ? null");
    expect(model).toContain("director_name: isIp ? null");
    expect(model).toContain("residence_address: isIp ? values.residenceAddress.trim() || null : null");
    expect(model).toContain("passport_details: isIp ? values.passportDetails.trim() || null : null");
  });

  it("supports file preview and requires explicit apply", () => {
    expect(resources).toContain("previewOrganizationImportFile");
    expect(resources).toContain("FormData");
    expect(smartImport).toContain('type="file"');
    expect(smartImport).toContain("previewOrganizationImportFile");
    expect(smartImport).toContain("Применить к форме");
    expect(smartImport).toContain("onApply(preview)");
  });
});
