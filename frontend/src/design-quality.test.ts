import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const saturation = s / 100;
  const lightness = l / 100;
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
  const x = chroma * (1 - Math.abs(((h / 60) % 2) - 1));
  const offset = lightness - chroma / 2;
  const [r, g, b] = h < 60 ? [chroma, x, 0] : h < 120 ? [x, chroma, 0] : h < 180 ? [0, chroma, x] : h < 240 ? [0, x, chroma] : h < 300 ? [x, 0, chroma] : [chroma, 0, x];
  return [r + offset, g + offset, b + offset];
}

function contrast(a: [number, number, number], b: [number, number, number]): number {
  const luminance = ([r, g, blue]: [number, number, number]) => {
    const linear = [r, g, blue].map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  };
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("design quality regressions", () => {
  it("keeps notification content within narrow viewports", () => {
    const notifications = source("src/components/notifications-popover.tsx");
    expect(notifications).toContain("w-[min(380px,calc(100vw-2rem))]");
  });

  it("localizes the theme toggle accessible name", () => {
    const toggle = source("src/components/theme-toggle.tsx");
    expect(toggle).toContain("Включить тёмную тему");
    expect(toggle).toContain("Включить светлую тему");
    expect(toggle).not.toContain('aria-label="Toggle theme"');
  });

  it("defines semantic colors and reduced-motion behavior centrally", () => {
    const css = source("src/app/globals.css");
    const config = source("tailwind.config.ts");
    expect(css).toContain("--semantic-info:");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(config).toContain('DEFAULT: "hsl(var(--semantic-info)');
  });

  it("keeps semantic text colors at WCAG AA contrast on muted surfaces", () => {
    const css = source("src/app/globals.css");
    for (const role of ["success", "warning", "danger", "info"]) {
      const foreground = css.match(new RegExp(`--semantic-${role}: (\\d+) (\\d+)% (\\d+)%`));
      const background = css.match(new RegExp(`--semantic-${role}-muted: (\\d+) (\\d+)% (\\d+)%`));
      expect(foreground, `${role} foreground token`).not.toBeNull();
      expect(background, `${role} muted token`).not.toBeNull();
      const fg = foreground!.slice(1).map(Number) as [number, number, number];
      const bg = background!.slice(1).map(Number) as [number, number, number];
      expect(contrast(hslToRgb(...fg), hslToRgb(...bg)), role).toBeGreaterThanOrEqual(4.5);
    }
  });
});
