"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { employeeLoad } from "@/lib/mock-data";

export function EmployeeLoad() {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={employeeLoad} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            interval={0}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted) / 0.5)" }}
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
              color: "hsl(var(--popover-foreground))",
            }}
          />
          <Bar
            dataKey="done"
            name="Выполнено"
            stackId="a"
            fill="hsl(var(--chart-2))"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="open"
            name="В работе"
            stackId="a"
            fill="hsl(var(--chart-1))"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
