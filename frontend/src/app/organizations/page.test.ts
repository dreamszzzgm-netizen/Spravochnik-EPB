import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organizations list page", () => {
  const page = source("src/app/organizations/page.tsx");

  it("does not hardcode the create button as disabled", () => {
    expect(page).not.toMatch(/disabled\s+title="Создание будет подключено на Stage 2"/);
  });

  it("renders the create button as a Link to /organizations/new", () => {
    expect(page).toContain('href="/organizations/new"');
  });

  it("uses shadcn Button with asChild for the create action", () => {
    expect(page).toContain('<Button size="sm" asChild>');
    expect(page).toContain('<Link href="/organizations/new"');
  });

  it("each organization row links to its detail page", () => {
    expect(page).toContain("href={`/organizations/${organization.id}`}");
  });

  it("organization rows use Link or anchor for navigation", () => {
    expect(page).toMatch(/<Link[^>]*href={`\/organizations\/\$\{organization\.id\}`}/);
  });
});
