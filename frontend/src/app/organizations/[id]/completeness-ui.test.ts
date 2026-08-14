import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("organization workspace completeness UI", () => {
  const page = source("src/app/organizations/[id]/page.tsx");

  it("maps 'complete' status to label 'Заполнено'", () => {
    expect(page).toContain("Заполнено");
    expect(page).toContain("complete");
  });

  it("maps 'needs_attention' status to label 'Требует внимания'", () => {
    expect(page).toContain("Требует внимания");
    expect(page).toContain("needs_attention");
  });

  it("maps 'missing_required' status to label with 'обязательные незаполненные поля'", () => {
    expect(page).toContain("missing_required");
    expect(page).toMatch(/обязательные незаполненные поля/i);
  });

  it("renders missing_required_fields list with field labels", () => {
    expect(page).toContain("missing_required_fields");
    expect(page).toContain("f.label");
    expect(page).toContain('key={f.code}');
  });

  it("renders warning_fields for needs_attention status", () => {
    expect(page).toContain("warning_fields");
    expect(page).toContain("Рекомендации");
  });

  it("does not collapse needs_attention and missing_required into a single label", () => {
    expect(page).not.toMatch(/Неполные реквизиты/);
    expect(page).not.toMatch(/Полные реквизиты/);
  });
});
