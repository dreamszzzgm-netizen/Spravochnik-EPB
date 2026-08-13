import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const read = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

describe("management document control", () => {
  const report = read("src/app/reports/page.tsx");
  const workspace = read("src/app/organizations/[id]/documents/page.tsx");
  const docs = read("src/app/organizations/[id]/_components/organization-documents.tsx");

  it("shows required control categories", () => {
    for (const label of [
      "Срок истёк",
      "Истекает ≤ 14 дней",
      "Истекает 15–40 дней",
      "Не загружен",
      "Срок не указан",
    ]) expect(report).toContain(label);
  });

  it("keeps document operations in organization workspace", () => {
    expect(workspace).toContain("Документы организации");
    expect(docs).toContain("uploadOrganizationDocument");
    expect(docs).toContain("organizationDocumentDownloadHref");
    expect(docs).toContain("deleteOrganizationDocument");
  });

  it("is explicit before document schema migration", () => {
    expect(report).toContain("Таблицы документов и требований комплектности ещё не развернуты");
    expect(docs).toContain("таблицы Documents ещё не развернуты миграцией");
  });
});
