import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization edit smart form", () => {
  const page = source("src/app/organizations/[id]/edit/page.tsx");

  it("switches legal entity and IP-only fields", () => {
    expect(page).toContain('orgType === "individual_entrepreneur"');
    expect(page).toContain('orgType !== "individual_entrepreneur"');
    expect(page).toContain("Место жительства");
    expect(page).toContain("Паспортные данные");
    expect(page).toContain("ОГРНИП");
    expect(page).toContain("КПП");
    expect(page).toContain("ОГРН");
  });

  it("loads and saves the IP profile fields", () => {
    expect(page).toContain("residence_address");
    expect(page).toContain("passport_series");
    expect(page).toContain("passport_number");
    expect(page).toContain("passport_issue_date");
    expect(page).toContain("passport_department_code");
    expect(page).toContain("bank_bik");
    expect(page).toContain("bank_account");
  });
});
