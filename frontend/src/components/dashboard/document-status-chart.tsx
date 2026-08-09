"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

import { documentValidityDistribution, type DocumentValidity } from "@/lib/mock-data";

const VALIDITY_COLORS: Record<DocumentValidity, string> = {
  Действителен: "hsl(var(--status-active))",
  "Срок истекает через 40 дней": "hsl(var(--status-expertise))",
  "Срок истекает через 14 дней": "hsl(var(--status-paused))",
  "Срок истек": "hsl(var(--status-terminated))",
};

const NEEDS_ATTENTION: DocumentValidity[] = [
  "Срок истекает через 40 дней",
  "Срок истекает через 14 дней",
  "Срок истек",
];

export function DocumentStatusChart() {
  const data = documentValidityDistribution.map((d) => ({
    name: d.status,
    value: d.count,
    fill: VALIDITY_COLORS[d.status],
  }));
  const total = data.reduce((s, d) => s + d.value, 0);
  const attention = data
    .filter((d) => NEEDS_ATTENTION.includes(d.name as DocumentValidity))
    .reduce((s, d) => s + d.value, 0);

  return (
    <div className="flex h-[260px] w-full flex-col gap-3">
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 36, bottom: 4, left: 4 }}
            barCategoryGap={10}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              axisLine={false}
              tickLine={false}
              width={168}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            />
            <Bar dataKey="value" radius={[4, 4, 4, 4]} barSize={20}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                className="fill-foreground"
                fontSize={11}
                formatter={(v: number) => (v > 0 ? v : "")}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">
        Всего <span className="font-medium text-foreground">{total}</span> документов ·
        требуют внимания сейчас{" "}
        <span className="font-medium text-foreground">{attention}</span>
      </p>
    </div>
  );
}
