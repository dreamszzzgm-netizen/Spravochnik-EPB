import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "src");
const PRODUCTION_ROOTS = [resolve(ROOT, "app"), resolve(ROOT, "components")];

function productionSources(): Array<{ path: string; source: string }> {
  const files: Array<{ path: string; source: string }> = [];

  function walk(directory: string) {
    for (const entry of readdirSync(directory)) {
      const path = join(directory, entry);
      const info = statSync(path);
      if (info.isDirectory()) {
        walk(path);
        continue;
      }
      if (!/\.(ts|tsx)$/.test(entry)) continue;
      files.push({
        path: relative(ROOT, path).replaceAll("\\", "/"),
        source: readFileSync(path, "utf8"),
      });
    }
  }

  for (const root of PRODUCTION_ROOTS) walk(root);
  return files;
}

describe("Pilot production UI contains no demo business data", () => {
  it("forbids mock-data imports from app and user-facing components", () => {
    const offenders = productionSources()
      .filter(({ source }) => source.includes("@/lib/mock-data"))
      .map(({ path }) => path);

    expect(offenders).toEqual([]);
  });

  it("does not expose known sample business identifiers", () => {
    const forbidden = ["npd-536", "npd-533", "gost-34347", "ЭПБ-2026/2401"];
    const offenders = productionSources()
      .filter(({ source }) => forbidden.some((value) => source.includes(value)))
      .map(({ path }) => path);

    expect(offenders).toEqual([]);
  });

  it("does not render the old global demo-mode warning", () => {
    const shell = readFileSync(resolve(ROOT, "components/app-shell.tsx"), "utf8");
    expect(shell).not.toContain("DemoDataNotice");
    expect(shell).not.toContain("Демо-режим");
  });

  it("does not hard-code task or expertise counters in the sidebar", () => {
    const sidebar = readFileSync(resolve(ROOT, "components/nav-sidebar.tsx"), "utf8");
    expect(sidebar).not.toContain('item.href === "/tasks" &&');
    expect(sidebar).not.toContain('item.href === "/expertise" &&');
  });
});
