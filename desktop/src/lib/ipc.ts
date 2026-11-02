import { invoke } from "@tauri-apps/api/core";

export type ISODate = string;

export interface Habit {
  id: number;
  name: string;
  position: number;
  archived: boolean;
}

export interface DayState {
  day: ISODate;
  habits: Habit[];
  completed: number[];
  target: number;
  note: string | null;
  streak: number;
}

export interface DaySummary {
  day: ISODate;
  count: number;
  target: number | null;
}

export interface Streak {
  current: number;
  best: number;
}

export type ThemeKey = "forest" | "ocean" | "violet" | "ember" | "mono" | "paper";

export interface Settings {
  theme: ThemeKey;
  startDate: ISODate;
  birthDate: ISODate;
  lifespan: number;
  weekStart: 0 | 1;
  reduceMotion: boolean;
  reminderEnabled: boolean;
  reminderTime: string;
  minimizeToTray: boolean;
  launchAtLogin: boolean;
  onboarded: boolean;
}

export interface SettingsPatch {
  theme?: ThemeKey;
  startDate?: ISODate;
  birthDate?: ISODate;
  lifespan?: number;
  weekStart?: 0 | 1;
  reduceMotion?: boolean;
  reminderEnabled?: boolean;
  reminderTime?: string;
  minimizeToTray?: boolean;
  launchAtLogin?: boolean;
  onboarded?: boolean;
}

export interface Bootstrap {
  settings: Settings;
  habits: Habit[];
  today: ISODate;
  streak: number;
  legacyAvailable: boolean;
  dataDir: string;
}

export interface HabitMark {
  habitId: number;
  day: ISODate;
}

export interface HabitStat {
  habitId: number;
  name: string;
  completions: number;
  rate: number;
}

export interface Stats {
  days: number;
  perfectDays: number;
  activeDays: number;
  rate: number;
  bestStreak: number;
  perHabit: HabitStat[];
}

export interface ImportResult {
  habits: number;
  completions: number;
  days: number;
  notes: number;
}

export const api = {
  bootstrap: () => invoke<Bootstrap>("bootstrap"),
  getDay: (day: ISODate) => invoke<DayState>("get_day", { day }),
  toggle: (habitId: number, day: ISODate) =>
    invoke<DayState>("toggle_completion", { habitId, day }),
  rangeSummary: (start: ISODate, end: ISODate) =>
    invoke<DaySummary[]>("range_summary", { start, end }),
  completionsRange: (start: ISODate, end: ISODate) =>
    invoke<HabitMark[]>("completions_range", { start, end }),
  listHabits: () => invoke<Habit[]>("list_habits"),
  listArchivedHabits: () => invoke<Habit[]>("list_archived_habits"),
  createHabit: (name: string) => invoke<Habit[]>("create_habit", { name }),
  renameHabit: (id: number, name: string) => invoke<Habit[]>("rename_habit", { id, name }),
  reorderHabits: (ids: number[]) => invoke<Habit[]>("reorder_habits", { ids }),
  archiveHabit: (id: number) => invoke<Habit[]>("archive_habit", { id }),
  restoreHabit: (id: number) => invoke<Habit[]>("restore_habit", { id }),
  deleteHabit: (id: number) => invoke<Habit[]>("delete_habit", { id }),
  getSettings: () => invoke<Settings>("get_settings"),
  updateSettings: (patch: SettingsPatch) => invoke<Settings>("update_settings", { patch }),
  streak: (through?: ISODate) => invoke<Streak>("streak", { through: through ?? null }),
  stats: (start: ISODate, end: ISODate) => invoke<Stats>("stats", { start, end }),
  getNote: (day: ISODate) => invoke<string | null>("get_note", { day }),
  setNote: (day: ISODate, body: string) =>
    invoke<string | null>("set_note", { day, body }),
  exportTo: (path: string) => invoke<string>("export_to", { path }),
  importFrom: (path: string) => invoke<ImportResult>("import_from", { path }),
  backupNow: () => invoke<string>("backup_now"),
  importLegacy: () => invoke<boolean>("import_legacy"),
};
