export const formatVal = (val: number | null | undefined): string => {
  if (val === null || val === undefined || typeof val !== "number" || isNaN(val)) return "-";
  return Math.round(val).toLocaleString();
};
