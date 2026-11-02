import {
  addDays,
  addMonths,
  addYears,
  differenceInCalendarDays,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  getDay,
  isSameDay,
  parseISO,
  startOfMonth,
  startOfWeek,
  subMonths,
  subYears,
} from "date-fns";

export const iso = (day: Date): string => format(day, "yyyy-MM-dd");
export const parse = (day: string): Date => parseISO(day);
export const todayISO = (): string => iso(new Date());

export function monthMatrix(month: Date, weekStart: 0 | 1): Date[] {
  const first = startOfMonth(month);
  const start = startOfWeek(first, { weekStartsOn: weekStart });
  return Array.from({ length: 42 }, (_, index) => addDays(start, index));
}

export function monthBounds(month: Date, weekStart: 0 | 1): { start: string; end: string } {
  const grid = monthMatrix(month, weekStart);
  return { start: iso(grid[0]), end: iso(grid[grid.length - 1]) };
}

export function weekdayLabels(weekStart: 0 | 1): string[] {
  const base = weekStart === 1 ? 1 : 0;
  return Array.from({ length: 7 }, (_, index) =>
    format(new Date(2024, 0, 7 + ((base + index) % 7)), "EEEEE"),
  );
}

export function lastSevenDays(end: Date): Date[] {
  return eachDayOfInterval({ start: addDays(end, -6), end });
}

export function weekOf(day: Date, weekStart: 0 | 1): Date[] {
  const start = startOfWeek(day, { weekStartsOn: weekStart });
  return eachDayOfInterval({ start, end: endOfWeek(day, { weekStartsOn: weekStart }) });
}

export function yearBounds(year: number): { start: string; end: string } {
  return {
    start: iso(new Date(year, 0, 1)),
    end: iso(new Date(year, 11, 31)),
  };
}

export function monthLabel(day: Date): string {
  return format(day, "MMMM yyyy");
}

export function shortDate(day: string): string {
  return format(parse(day), "MMM d");
}

export function longDate(day: string): string {
  return format(parse(day), "EEEE, MMMM d, yyyy");
}

export function weekday(day: Date): number {
  return getDay(day);
}

export const dateMath = {
  addDays,
  addMonths,
  addYears,
  subMonths,
  subYears,
  differenceInCalendarDays,
  isSameDay,
  startOfMonth,
  endOfMonth,
};
