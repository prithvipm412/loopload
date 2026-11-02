export const num = (n: number, d = 0) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: d });
export const money = (n: number) => `₹${num(n)}`;
export const compact = (n: number) =>
  Math.abs(n) >= 1e7
    ? `₹${num(n / 1e7, 2)} Cr`
    : Math.abs(n) >= 1e5
      ? `₹${num(n / 1e5, 2)} L`
      : money(n);
export const dayTime = (h: number) =>
  `${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][Math.min(6, Math.floor(h / 24))]} ${String(Math.floor(h % 24)).padStart(2, "0")}:${String(Math.round((h % 1) * 60) % 60).padStart(2, "0")}`;
