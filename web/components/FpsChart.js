"use client";

import { useT } from "@/lib/locale";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Average and 1% low side by side. Two bars rather than one range: the floor is the number
// that decides whether a game feels smooth, so it gets a bar and a label of its own instead
// of being implied by the bottom of a range. A combination the source has no low for draws
// no second bar, and the line above the chart says why.
export default function FpsChart({ rows }) {
  const t = useT();
  const data = rows.map((row) => ({
    label: row.label,
    avg: row.avg,
    low: row.low ?? null,
  }));

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#2a2f3a" />
          <XAxis type="number" stroke="#8b93a7" />
          <YAxis type="category" dataKey="label" width={130} stroke="#8b93a7" />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{ background: "#151922", border: "1px solid #2a2f3a" }}
            formatter={(value, name) => [value === null || value === undefined ? "—" : `${value} FPS`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="avg" name={t.fps.average} fill="#4f8cff" radius={[0, 4, 4, 0]} isAnimationActive={false} />
          <Bar dataKey="low" name={t.fps.low1} fill="#8b93a7" radius={[0, 4, 4, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
