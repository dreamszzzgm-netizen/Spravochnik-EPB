import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization smart form", () => {
  const page = source("src/app/organizations/new/page.tsx");

  it("renders IP-only requisites conditionally", () => {
    expect(page).toContain('orgType === "individual_entrepreneur"');
    expect(page).toContain("Место жительства");
    expect(page).toContain("Паспортные данные");
    expect(page).toContain("ОГРНИП");
  });

  it("does not render KPP and OGRN as unconditional identifier inputs", () => {
    expect(page).toContain('orgType !== "individual_entrepreneur"');
    expect(page).toContain("КПП");
    expect(page).toContain("ОГРН");
  });

  it("offers smart import before manual save", () => {
    expect(page).toContain("Умный импорт");
    expect(page).toContain("Проверить распознанные данные");
  });
});
