"use client";

import { formatEuros } from "@/lib/api";
import { useT } from "@/lib/locale";

export default function PartsTable({ parts }) {
  const t = useT();
  return (
    <table className="parts">
      <thead>
        <tr>
          <th>{t.result.table.part}</th>
          <th>{t.result.table.product}</th>
          <th>{t.result.table.shop}</th>
          <th className="right">{t.result.table.price}</th>
        </tr>
      </thead>
      <tbody>
        {parts.map((part) => (
          <tr key={part.category}>
            <td className="muted">{t.categories[part.category] ?? part.category}</td>
            <td>
              <a href={part.url} target="_blank" rel="noopener noreferrer">
                {part.name}
              </a>
            </td>
            <td>{part.shop}</td>
            <td className="right">{formatEuros(part.priceCents, t.locale)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
