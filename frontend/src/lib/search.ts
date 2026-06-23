/** Filter an array of row objects by a free-text query across all values. */
export function filterByQuery<T extends Record<string, any>>(rows: T[] | undefined, q: string): T[] {
  if (!rows) return [];
  const ql = q.trim().toLowerCase();
  if (!ql) return rows;
  return rows.filter((r) => Object.values(r).join(" ").toLowerCase().includes(ql));
}
