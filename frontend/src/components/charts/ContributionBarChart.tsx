"use client";

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function pctLabel(value: unknown) {
  if (typeof value !== "number") return "";
  return `${value.toFixed(1)}%`;
}

export default function ContributionBarChart({ data }: { data: Array<{ student: string; percentage: number }> }) {
  return (
    <div className="chart-wrap">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 28, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ececec" vertical={false} />
          <XAxis dataKey="student" tick={{ fontSize: 12, fill: "#525252" }} interval={0} height={56} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} tick={{ fontSize: 11, fill: "#a3a3a3" }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, "Contribution"]} />
          <Bar dataKey="percentage" fill="#111111" radius={[6, 6, 0, 0]} maxBarSize={56}>
            <LabelList dataKey="percentage" position="top" formatter={pctLabel} style={{ fontSize: 11, fill: "#111" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
