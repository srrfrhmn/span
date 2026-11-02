import { create } from "zustand";
import { todayISO } from "../lib/dates";
import {
  api,
  type DayState,
  type Habit,
  type ISODate,
  type Settings,
  type SettingsPatch,
} from "../lib/ipc";

export type View = "today" | "month" | "year" | "life" | "settings";

export interface Toast {
  id: number;
  message: string;
  tone: "info" | "success" | "error";
}

export const fallbackSettings: Settings = {
  theme: "forest",
  startDate: todayISO(),
  birthDate: "1996-01-01",
  lifespan: 85,
  weekStart: 1,
  reduceMotion: false,
  reminderEnabled: false,
  reminderTime: "20:00",
  minimizeToTray: true,
  launchAtLogin: false,
  onboarded: false,
};

export function applyTheme(settings: Settings): void {
  const root = document.documentElement;
  root.dataset.theme = settings.theme;
  root.dataset.motion = settings.reduceMotion ? "reduced" : "full";
  root.style.colorScheme = settings.theme === "paper" ? "light" : "dark";
}

export function errorMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}

interface AppStore {
  ready: boolean;
  error: string | null;
  view: View;
  selectedDay: ISODate;
  today: ISODate;
  settings: Settings;
  habits: Habit[];
  archived: Habit[];
  day: DayState | null;
  streak: number;
  legacyAvailable: boolean;
  dataDir: string;
  dataVersion: number;
  toasts: Toast[];
  paletteOpen: boolean;
  init: () => Promise<void>;
  reload: () => Promise<void>;
  loadDay: (day: ISODate) => Promise<void>;
  selectDay: (day: ISODate) => Promise<void>;
  setView: (view: View) => void;
  toggle: (habitId: number) => Promise<void>;
  saveSettings: (patch: SettingsPatch) => Promise<Settings>;
  addHabit: (name: string) => Promise<void>;
  renameHabit: (id: number, name: string) => Promise<void>;
  reorderHabits: (ids: number[]) => Promise<void>;
  archiveHabit: (id: number) => Promise<void>;
  restoreHabit: (id: number) => Promise<void>;
  deleteHabit: (id: number) => Promise<void>;
  loadArchived: () => Promise<void>;
  setNote: (day: ISODate, body: string) => Promise<void>;
  toast: (message: string, tone?: Toast["tone"]) => void;
  dismissToast: (id: number) => void;
  setPalette: (open: boolean) => void;
}

let toastId = 0;

export const useApp = create<AppStore>((set, get) => ({
  ready: false,
  error: null,
  view: "today",
  selectedDay: todayISO(),
  today: todayISO(),
  settings: fallbackSettings,
  habits: [],
  archived: [],
  day: null,
  streak: 0,
  legacyAvailable: false,
  dataDir: "",
  dataVersion: 0,
  toasts: [],
  paletteOpen: false,

  init: async () => {
    try {
      const boot = await api.bootstrap();
      applyTheme(boot.settings);
      set({
        ready: true,
        error: null,
        settings: boot.settings,
        habits: boot.habits,
        today: boot.today,
        selectedDay: boot.today,
        view: "today",
        streak: boot.streak,
        legacyAvailable: boot.legacyAvailable,
        dataDir: boot.dataDir,
      });
      const day = await api.getDay(boot.today);
      set({ day, streak: day.streak });
    } catch (error) {
      set({ ready: true, error: errorMessage(error) });
    }
  },

  reload: async () => {
    const boot = await api.bootstrap();
    applyTheme(boot.settings);
    // After midnight, someone looking at "today" should land on the new today.
    const wasOnToday = get().selectedDay === get().today;
    set({
      settings: boot.settings,
      habits: boot.habits,
      today: boot.today,
      selectedDay: wasOnToday ? boot.today : get().selectedDay,
      streak: boot.streak,
      legacyAvailable: boot.legacyAvailable,
      dataDir: boot.dataDir,
      dataVersion: get().dataVersion + 1,
    });
    const day = await api.getDay(get().selectedDay);
    set({ day, streak: day.streak });
    if (get().view === "settings") {
      await get().loadArchived();
    }
  },

  loadDay: async (day) => {
    try {
      const state = await api.getDay(day);
      set({ day: state, selectedDay: state.day, streak: state.streak });
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  selectDay: async (day) => {
    set({ selectedDay: day, view: "today" });
    await get().loadDay(day);
  },

  setView: (view) => set({ view }),

  toggle: async (habitId) => {
    const current = get().day;
    if (!current) return;
    const completed = new Set(current.completed);
    const wasDone = completed.has(habitId);
    if (wasDone) completed.delete(habitId);
    else completed.add(habitId);
    set({
      day: { ...current, completed: [...completed].sort((a, b) => a - b) },
    });
    try {
      const fresh = await api.toggle(habitId, current.day);
      set({
        day: fresh,
        streak: fresh.streak,
        dataVersion: get().dataVersion + 1,
      });
      if (!wasDone && fresh.target > 0 && fresh.completed.length >= fresh.target) {
        get().toast("Every promise kept. Perfect day.", "success");
      }
    } catch (error) {
      set({ day: current });
      get().toast(errorMessage(error), "error");
    }
  },

  saveSettings: async (patch) => {
    const settings = await api.updateSettings(patch);
    set({ settings });
    applyTheme(settings);
    return settings;
  },

  addHabit: async (name) => {
    try {
      const habits = await api.createHabit(name);
      set({ habits, dataVersion: get().dataVersion + 1 });
      await get().loadDay(get().selectedDay);
    } catch (error) {
      get().toast(errorMessage(error), "error");
      throw error;
    }
  },

  renameHabit: async (id, name) => {
    try {
      const habits = await api.renameHabit(id, name);
      set({ habits });
      await get().loadDay(get().selectedDay);
    } catch (error) {
      get().toast(errorMessage(error), "error");
      throw error;
    }
  },

  reorderHabits: async (ids) => {
    const optimistic = ids
      .map((id) => get().habits.find((habit) => habit.id === id))
      .filter((habit): habit is Habit => Boolean(habit));
    set({ habits: optimistic });
    try {
      const habits = await api.reorderHabits(ids);
      set({ habits });
    } catch (error) {
      set({ habits: await api.listHabits() });
      get().toast(errorMessage(error), "error");
    }
  },

  archiveHabit: async (id) => {
    try {
      const habits = await api.archiveHabit(id);
      set({ habits, dataVersion: get().dataVersion + 1 });
      await get().loadArchived();
      await get().loadDay(get().selectedDay);
      get().toast("Habit archived. Its history is still here.", "info");
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  restoreHabit: async (id) => {
    try {
      const habits = await api.restoreHabit(id);
      set({ habits, dataVersion: get().dataVersion + 1 });
      await get().loadArchived();
      get().toast("Habit restored.", "success");
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  deleteHabit: async (id) => {
    try {
      const habits = await api.deleteHabit(id);
      set({ habits, dataVersion: get().dataVersion + 1 });
      await get().loadArchived();
      get().toast("Habit deleted.", "info");
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  loadArchived: async () => {
    try {
      const archived = await api.listArchivedHabits();
      set({ archived });
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  setNote: async (day, body) => {
    try {
      const note = await api.setNote(day, body);
      set((state) =>
        state.day && state.day.day === day
          ? { day: { ...state.day, note } }
          : state,
      );
    } catch (error) {
      get().toast(errorMessage(error), "error");
    }
  },

  toast: (message, tone = "info") => {
    const id = ++toastId;
    set((state) => ({ toasts: [...state.toasts, { id, message, tone }] }));
    window.setTimeout(() => get().dismissToast(id), 4200);
  },

  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),

  setPalette: (open) => set({ paletteOpen: open }),
}));
