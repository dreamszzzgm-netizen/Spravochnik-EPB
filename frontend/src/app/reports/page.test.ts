import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("management reports page", () => {
  it("is exposed in main navigation", () => {
    const navigation = source("src/components/nav-config.ts");
    expect(navigation).toContain('href: "/reports"');
    expect(navigation).toContain('label: "Отчёты"');
  });

  it("has a dedicated reports page", () => {
    const pagePath = resolve(process.cwd(), "src/app/reports/page.tsx");
    expect(existsSync(pagePath)).toBe(true);
  });

  it("shows document control without demo figures", () => {
    const pagePath = "src/app/reports/page.tsx";
    if (!existsSync(resolve(process.cwd(), pagePath))) return;
    const page = source(pagePath);
    expect(page).toContain("Контроль документов");
    expect(page).toContain("Источник документов ещё не подключён");
    expect(page).not.toContain("mockDocuments");
  });
});
