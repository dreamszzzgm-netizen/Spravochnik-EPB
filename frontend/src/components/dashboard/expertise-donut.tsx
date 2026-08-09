"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { expertiseStatusDistribution, type ExpertiseStage } from "@/lib/mock-data";

const STATUS_COLORS: Record<ExpertiseStage, string> = {
  "Планируется выезд": "hsl(var(--status-draft))",
  "В работе": "hsl(var(--status-expertise))",
  "На регистрации в РТН": "hsl(var(--status-rtn))",
  Зарегистрирована: "hsl(var(--status-registered))",
};

type DonutDatum = {
  name: string;
  value: number;
  fill: string;
};

function DonutTooltip({ active, payload, total }: {
  active?: boolean;
  payload?: { payload: DonutDatum }[];
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const pct = total > 0 ? Math.round((d.value / total) * 100) : 0;
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2 text-xs shadow-md">
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-sm"
          style={{ backgroundColor: d.fill }}
        />
        <span className="font-medium text-foreground">{d.name}</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        {d.value} экспертиз · {pct}%
      </div>
    </div>
  );
}

export function ExpertiseDonut() {
  const data: DonutDatum[] = expertiseStatusDistribution.map((d) => ({
    name: d.status,
    value: d.count,
    fill: STATUS_COLORS[d.status],
  }));
  const total = data.reduce((s, d) => s + d.value, 0);
  const registered = data.find((d) => d.name === "Зарегистрирована")?.value ?? 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative mx-auto h-[180px] w-[180px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip
                cursor={{ fill: "transparent" }}
                content={<DonutTooltip total={total} />}
              />
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={56}
                outerRadius={84}
                strokeWidth={2}
                stroke="hsl(var(--background))"
                paddingAngle={2}
                isAnimationActive={false}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold tracking-tight text-foreground">{total}</span>
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
              экспертиз
            </span>
          </div>
        </div>

        <ul className="flex-1 space-y-2">
          {data.map((d) => {
            const pct = total > 0 ? Math.round((d.value / total) * 100) : 0;
            return (
              <li
                key={d.name}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: d.fill }}
                  />
                  <span className="truncate text-foreground">{d.name}</span>
                </div>
                <div className="flex shrink-0 items-baseline gap-2">
                  <span className="font-medium tabular-nums text-foreground">{d.value}</span>
                  <span className="text-xs tabular-nums text-muted-foreground">·</span>
                  <span className="text-xs tabular-nums text-muted-foreground">{pct}%</span>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
      <p className="text-xs text-muted-foreground">
        Из {total} экспертиз{" "}
        <span className="font-medium text-foreground">{registered}</span> зарегистрированы в РТН
      </p>
    </div>
  );
}
