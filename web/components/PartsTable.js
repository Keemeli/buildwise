"use client";

import { formatEuros } from "@/lib/api";
import { exactName, partLabel } from "@/lib/labels";
import ShopBadge from "@/components/ShopBadge";
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
              <a href={part.url} target="_blank" rel="noopener noreferrer" title={exactName(part)}>
                {partLabel(part)}
              </a>
              {/* The shop's own wording stays one line below: the label above is derived
                  from parsed specs and must never be the only name a part is known by. */}
              {exactName(part) && exactName(part) !== partLabel(part) && (
                <div className="muted small">{exactName(part)}</div>
              )}
            </td>
            <td><ShopBadge shop={part.shop} /></td>
            <td className="right">{formatEuros(part.priceCents, t.locale)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
