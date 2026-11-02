import { useCallback, useEffect } from "react";
import { addDays, isAfter } from "date-fns";
import { AlertTriangle, RotateCw } from "lucide-react";
import { CommandPalette } from "./components/CommandPalette";
import { Sidebar } from "./components/Sidebar";
import { TitleBar } from "./components/TitleBar";
import { Toasts } from "./components/Toasts";
import { useReminder } from "./hooks/useReminder";
import { iso, parse, todayISO } from "./lib/dates";
import { useApp } from "./state/store";
import { LifeView } from "./views/LifeView";
import { MonthView } from "./views/MonthView";
import { Onboarding } from "./views/Onboarding";
import { SettingsView } from "./views/SettingsView";
import { TodayView } from "./views/TodayView";
import { YearView } from "./views/YearView";

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    target.isContentEditable
  );
}

export default function App() {
  const ready = useApp((state) => state.ready);
  const error = useApp((state) => state.error);
  const init = useApp((state) => state.init);
  const reload = useApp((state) => state.reload);
  const view = useApp((state) => state.view);
  const settings = useApp((state) => state.settings);
  const selectedDay = useApp((state) => state.selectedDay);
  const today = useApp((state) => state.today);
  const paletteOpen = useApp((state) => state.paletteOpen);
  const setPalette = useApp((state) => state.setPalette);
  const selectDay = useApp((state) => state.selectDay);

  useReminder();

  useEffect(() => {
    void init();
  }, [init]);

  // Roll the app over at midnight without a restart.
  useEffect(() => {
    const handle = window.setInterval(() => {
      const now = todayISO();
      if (now !== useApp.getState().today) {
        void reload();
      }
    }, 60_000);
    return () => window.clearInterval(handle);
  }, [reload]);

  const step = useCallback(
    (offset: number) => {
      const state = useApp.getState();
      const current = state.selectedDay;
      const next = iso(addDays(parse(current), offset));
      if (offset > 0 && isAfter(parse(next), parse(state.today))) return;
      void selectDay(next);
    },
    [selectDay],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.ctrlKey || event.metaKey;
      if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette(!useApp.getState().paletteOpen);
        return;
      }
      if (event.key === "Escape" && useApp.getState().paletteOpen) {
        setPalette(false);
        return;
      }
      if (useApp.getState().paletteOpen || isTyping(event.target)) return;

      if (event.key.toLowerCase() === "t") {
        event.preventDefault();
        void selectDay(useApp.getState().today);
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        step(-1);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        step(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectDay, setPalette, step]);

  useEffect(() => {
    document.title = view === "settings" ? "Preferences · span" : "span";
  }, [view]);

  if (!ready) {
    return (
      <div className="boot">
        <TitleBar />
        <div className="boot__body">
          <span className="mark mark--large">s</span>
          <p>Gathering your days…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="boot">
        <TitleBar />
        <div className="boot__body boot__body--error">
          <AlertTriangle size={22} />
          <h1>span could not open its database.</h1>
          <p>{error}</p>
          <button className="btn primary" onClick={() => void init()}>
            <RotateCw size={15} /> Try again
          </button>
        </div>
        <Toasts />
      </div>
    );
  }

  if (!settings.onboarded) {
    return (
      <div className="app">
        <TitleBar />
        <Onboarding />
        <Toasts />
      </div>
    );
  }

  return (
    <div className="app">
      <TitleBar />
      <div className="workspace">
        <Sidebar />
        <main className="main" key={view}>
          {view === "today" ? <TodayView /> : null}
          {view === "month" ? <MonthView /> : null}
          {view === "year" ? <YearView /> : null}
          {view === "life" ? <LifeView /> : null}
          {view === "settings" ? <SettingsView /> : null}
        </main>
      </div>
      {paletteOpen ? <CommandPalette /> : null}
      <Toasts />
      <span className="sr-only" aria-live="polite">
        {view === "today" ? `Day selected: ${selectedDay}` : `${view} view`}
        {selectedDay === today ? " (today)" : ""}
      </span>
    </div>
  );
}
