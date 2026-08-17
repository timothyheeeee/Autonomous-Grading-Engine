"use client";

import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const PALETTE = ["#111111", "#737373", "#a3a3a3", "#0f766e", "#44403c"];

function pctLabel(value: unknown) {
  if (typeof value !== "number") return "";
  return `${value.toFixed(1)}%`;
}

export default function CriterionChart({
  students,
}: {
  students: Array<{
    student_name: string;
    criteria: Array<{ criterion: string; percentage: number }>;
  }>;
}) {
  const names = Array.from(new Set(students.flatMap((row) => row.criteria.map((item) => item.criterion))));
  const data = students.map((row) => {
    const point: Record<string, string | number> = { student: row.student_name };
    for (const name of names) {
      point[name] = row.criteria.find((item) => item.criterion === name)?.percentage ?? 0;
    }
    return point;
  });

  return (
    <div className="h-[400px] w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 28, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ececec" vertical={false} />
          <XAxis dataKey="student" tick={{ fontSize: 12, fill: "#525252" }} interval={0} height={56} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} tick={{ fontSize: 11, fill: "#a3a3a3" }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(value: number, name) => [`${Number(value).toFixed(1)}%`, name]} />
          <Legend />
          {names.map((name, index) => (
            <Bar key={name} dataKey={name} fill={PALETTE[index % PALETTE.length]} radius={[4, 4, 0, 0]}>
              <LabelList dataKey={name} position="top" formatter={pctLabel} style={{ fontSize: 10, fill: "#111" }} />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
