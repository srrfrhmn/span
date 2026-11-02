import { describe, expect, it } from "vitest";
import { heatLevel } from "./heat";

describe("heatLevel", () => {
  it("is empty with nothing done or nothing to do", () => {
    expect(heatLevel(0, 4)).toBe(0);
    expect(heatLevel(2, 0)).toBe(0);
    expect(heatLevel(0, 0)).toBe(0);
  });

  it("steps through the five filled levels", () => {
    expect(heatLevel(1, 10)).toBe(1);
    expect(heatLevel(3, 10)).toBe(2);
    expect(heatLevel(5, 10)).toBe(3);
    expect(heatLevel(8, 10)).toBe(4);
  });

  it("caps at five once the target is met or beaten", () => {
    expect(heatLevel(10, 10)).toBe(5);
    expect(heatLevel(14, 10)).toBe(5);
  });

  it("treats one of one as a full day", () => {
    expect(heatLevel(1, 1)).toBe(5);
  });
});
