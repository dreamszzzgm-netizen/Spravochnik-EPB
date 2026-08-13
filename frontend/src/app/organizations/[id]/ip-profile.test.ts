import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization IP profile card", () => {
  const page = source("src/app/organizations/[id]/page.tsx");

  it("shows IP-specific profile details only for individual entrepreneurs", () => {
    expect(page).toContain('org.organization_type === "individual_entrepreneur"');
    expect(page).toContain("Место жительства");
    expect(page).toContain("Паспортные данные");
    expect(page).toContain("Серия и номер");
    expect(page).toContain("Код подразделения");
  });

  it("shows bank requisites stored on the organization", () => {
    expect(page).toContain("Банковские реквизиты");
    expect(page).toContain("org.bank_name");
    expect(page).toContain("org.bank_bik");
    expect(page).toContain("org.bank_account");
    expect(page).toContain("org.correspondent_account");
  });
});
