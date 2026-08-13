import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const read = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

describe("expertise real data slice", () => {
  const list = read("src/app/expertise/page.tsx");
  const detail = read("src/app/expertise/[id]/_components/expertise-detail.tsx");
  const create = read("src/app/expertise/new/page.tsx");
  const api = read("src/lib/api/expertises.ts");

  it("list page uses the real API and not mock data", () => {
    expect(list).toContain("getExpertises");
    expect(list).not.toContain("expertiseList");
    expect(list).not.toContain("@/lib/mock-data");
  });

  it("detail page loads expertise and status history from the API", () => {
    expect(detail).toContain("getExpertise(");
    expect(detail).toContain("getExpertiseStatusHistory");
    expect(detail).toContain("История статусов");
    expect(detail).not.toContain("@/lib/mock-data");
  });

  it("create page posts through the real API", () => {
    expect(create).toContain("createExpertise(");
    expect(create).toContain("listContracts");
    expect(create).toContain("listExpertiseTypes");
    expect(create).toContain("responsible_expert_id");
    expect(create).not.toContain("@/lib/mock-data");
  });

  it("exposes status machine values and labels", () => {
    expect(api).toContain("preparation");
    expect(api).toContain("ready_for_registration");
    expect(api).toContain("received_by_customer");
    expect(api).toContain("EXPERTISE_STATUS_LABELS");
    expect(api).toContain("changeExpertiseStatus");
  });
});
