import { describe, it, expect } from "vitest";
import { formatVal } from "./format";

describe("formatVal utility", () => {
  it("should format valid numbers using toLocaleString", () => {
    expect(formatVal(1000)).toBe("1,000");
    expect(formatVal(0)).toBe("0");
  });

  it("should return '-' for null or undefined", () => {
    expect(formatVal(null)).toBe("-");
    expect(formatVal(undefined)).toBe("-");
  });

  it("should return '-' for NaN", () => {
    expect(formatVal(NaN)).toBe("-");
  });
});
