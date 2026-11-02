import { describe, expect, it } from "vitest";
import {
  dateMath,
  iso,
  lastSevenDays,
  monthBounds,
  monthMatrix,
  parse,
  weekdayLabels,
  weekOf,
  yearBounds,
} from "./dates";

describe("iso / parse", () => {
  it("keeps local calendar days intact", () => {
    expect(iso(new Date(2026, 10, 2))).toBe("2026-11-02");
    expect(iso(parse("2026-11-02"))).toBe("2026-11-02");
  });
});

describe("monthMatrix", () => {
  it("always returns a six-week grid starting on the chosen weekday", () => {
    const grid = monthMatrix(new Date(2026, 10, 1), 1);
    expect(grid).toHaveLength(42);
    expect(grid[0].getDay()).toBe(1);
    expect(iso(grid[0])).toBe("2026-10-26");
  });

  it("starts on Sunday when asked", () => {
    const grid = monthMatrix(new Date(2026, 10, 1), 0);
    expect(grid[0].getDay()).toBe(0);
    expect(iso(grid[0])).toBe("2026-11-01");
  });
});

describe("bounds", () => {
  it("covers the whole visible month grid", () => {
    const bounds = monthBounds(new Date(2026, 1, 15), 1);
    expect(bounds.start).toBe("2026-01-26");
    expect(bounds.end).toBe("2026-03-08");
  });

  it("spans a calendar year", () => {
    expect(yearBounds(2026)).toEqual({ start: "2026-01-01", end: "2026-12-31" });
  });
});

describe("week helpers", () => {
  it("returns exactly seven days ending on the given day", () => {
    const days = lastSevenDays(parse("2026-11-02"));
    expect(days).toHaveLength(7);
    expect(iso(days[0])).toBe("2026-10-27");
    expect(iso(days[6])).toBe("2026-11-02");
  });

  it("builds a Monday-first week", () => {
    const days = weekOf(parse("2026-11-02"), 1);
    expect(iso(days[0])).toBe("2026-11-02");
    expect(iso(days[6])).toBe("2026-11-08");
  });

  it("labels weekdays from the configured start", () => {
    expect(weekdayLabels(1)).toHaveLength(7);
    expect(weekdayLabels(1)[0]).toBe("M");
    expect(weekdayLabels(0)[0]).toBe("S");
  });
});

describe("dateMath", () => {
  it("counts calendar days across month boundaries", () => {
    expect(
      dateMath.differenceInCalendarDays(parse("2026-12-01"), parse("2026-11-01")),
    ).toBe(30);
  });
});
