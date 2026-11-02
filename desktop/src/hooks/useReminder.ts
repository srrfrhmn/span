import { useEffect } from "react";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";
import { api } from "../lib/ipc";
import { todayISO } from "../lib/dates";
import { useApp } from "../state/store";

const LAST_KEY = "span.reminder.last";

function minutesOf(value: string): number {
  const [hours, minutes] = value.split(":").map(Number);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return -1;
  return hours * 60 + minutes;
}

/**
 * Fires one native notification a day, after the chosen time, when the day is
 * still unfinished. Runs only while the app is alive (tray included).
 */
export function useReminder() {
  const settings = useApp((state) => state.settings);
  const ready = useApp((state) => state.ready);
  const settingsKey = `${settings.reminderEnabled}|${settings.reminderTime}`;

  useEffect(() => {
    if (!ready || !settings.reminderEnabled) return;
    let cancelled = false;

    const check = async () => {
      const today = todayISO();
      if (window.localStorage.getItem(LAST_KEY) === today) return;
      const now = new Date();
      if (now.getHours() * 60 + now.getMinutes() < minutesOf(settings.reminderTime)) return;

      try {
        let granted = await isPermissionGranted();
        if (!granted) {
          granted = (await requestPermission()) === "granted";
        }
        if (!granted || cancelled) return;

        const day = await api.getDay(today);
        if (cancelled) return;
        const remaining = Math.max(0, day.target - day.completed.length);
        if (remaining === 0 || day.target === 0) return;

        sendNotification({
          title: "A quiet nudge from span",
          body:
            remaining === 1
              ? "One habit is still open today."
              : `${remaining} habits are still open today.`,
        });
        window.localStorage.setItem(LAST_KEY, today);
      } catch {
        // Notifications are best-effort; never interrupt the app for them.
      }
    };

    void check();
    const handle = window.setInterval(() => void check(), 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [ready, settingsKey, settings.reminderEnabled, settings.reminderTime]);
}
