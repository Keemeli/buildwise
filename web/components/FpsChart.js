"use client";

import { useT } from "@/lib/locale";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Draws the FPS range as bars: an invisible bar from 0 to min,
// with a visible bar from min to max stacked on top.
export default function FpsChart({ fps }) {
  const t = useT();
  const data = fps.map((row) => ({
    label: `${row.resolution} ${t.fps.settings[row.settings] ?? row.settings}`,
    base: row.min,
    range: row.max - row.min,
    min: row.min,
    max: row.max,
  }));

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#2a2f3a" />
          <XAxis type="number" stroke="#8b93a7" />
          <YAxis type="category" dataKey="label" width={110} stroke="#8b93a7" />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{ background: "#151922", border: "1px solid #2a2f3a" }}
            formatter={(_, __, item) => [`${item.payload.min}–${item.payload.max} FPS`, t.fps.estimate]}
          />
          <Bar dataKey="base" stackId="fps" fill="transparent" tooltipType="none" isAnimationActive={false} />
          <Bar dataKey="range" stackId="fps" fill="#4f8cff" radius={[0, 6, 6, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
