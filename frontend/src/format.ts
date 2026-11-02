export const num = (n: number, d = 0) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: d });
export const money = (n: number) => `₹${num(n)}`;
export const compact = (n: number) =>
  Math.abs(n) >= 1e7
    ? `₹${num(n / 1e7, 2)} Cr`
    : Math.abs(n) >= 1e5
      ? `₹${num(n / 1e5, 2)} L`
      : money(n);
export const dayTime = (h: number) => {
  const minutes = Math.round(h * 60);
  const day = Math.floor(minutes / 1440);
  return `${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day % 7]} ${String(Math.floor(minutes / 60) % 24).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}${day >= 7 ? ` (+${Math.floor(day / 7)}w)` : ""}`;
};
