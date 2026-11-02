import { confirm, open, save } from "@tauri-apps/plugin-dialog";
import {
  disable as disableAutostart,
  enable as enableAutostart,
  isEnabled as isAutostartEnabled,
} from "@tauri-apps/plugin-autostart";
import {
  isPermissionGranted,
  requestPermission,
} from "@tauri-apps/plugin-notification";
import {
  Archive,
  ArrowDown,
  ArrowUp,
  Bell,
  Check,
  Copy,
  Database,
  Download,
  GripVertical,
  HardDriveDownload,
  Plus,
  Power,
  RotateCcw,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { ThemePicker } from "../components/ThemePicker";
import { Toggle } from "../components/Toggle";
import { todayISO } from "../lib/dates";
import { api, type ThemeKey } from "../lib/ipc";
import { errorMessage, useApp } from "../state/store";

const MAX_HABITS = 10;

export function SettingsView() {
  const settings = useApp((state) => state.settings);
  const habits = useApp((state) => state.habits);
  const archived = useApp((state) => state.archived);
  const dataDir = useApp((state) => state.dataDir);
  const legacyAvailable = useApp((state) => state.legacyAvailable);
  const saveSettings = useApp((state) => state.saveSettings);
  const addHabit = useApp((state) => state.addHabit);
  const renameHabit = useApp((state) => state.renameHabit);
  const reorderHabits = useApp((state) => state.reorderHabits);
  const archiveHabit = useApp((state) => state.archiveHabit);
  const restoreHabit = useApp((state) => state.restoreHabit);
  const deleteHabit = useApp((state) => state.deleteHabit);
  const loadArchived = useApp((state) => state.loadArchived);
  const reload = useApp((state) => state.reload);
  const toast = useApp((state) => state.toast);

  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [newHabit, setNewHabit] = useState("");
  const [dragId, setDragId] = useState<number | null>(null);
  const [birth, setBirth] = useState(settings.birthDate);
  const [lifespan, setLifespan] = useState(String(settings.lifespan));
  const [weekStart, setWeekStart] = useState<0 | 1>(settings.weekStart);
  const [launchAtLogin, setLaunchAtLogin] = useState(settings.launchAtLogin);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDrafts(Object.fromEntries(habits.map((habit) => [habit.id, habit.name])));
  }, [habits]);

  useEffect(() => {
    setBirth(settings.birthDate);
    setLifespan(String(settings.lifespan));
    setWeekStart(settings.weekStart);
  }, [settings.birthDate, settings.lifespan, settings.weekStart]);

  useEffect(() => {
    void loadArchived();
  }, [loadArchived]);

  useEffect(() => {
    void isAutostartEnabled()
      .then((enabled) => setLaunchAtLogin(enabled))
      .catch(() => undefined);
  }, []);

  const pickTheme = (theme: ThemeKey) => {
    void saveSettings({ theme }).catch((error) => toast(errorMessage(error), "error"));
  };

  const commitName = async (id: number) => {
    const habit = habits.find((entry) => entry.id === id);
    const draft = (drafts[id] ?? "").trim();
    if (!habit) return;
    if (!draft) {
      setDrafts((current) => ({ ...current, [id]: habit.name }));
      return;
    }
    if (draft !== habit.name) {
      try {
        await renameHabit(id, draft);
      } catch {
        setDrafts((current) => ({ ...current, [id]: habit.name }));
      }
    }
  };

  const move = (id: number, delta: number) => {
    const index = habits.findIndex((habit) => habit.id === id);
    const next = index + delta;
    if (index < 0 || next < 0 || next >= habits.length) return;
    const ids = habits.map((habit) => habit.id);
    [ids[index], ids[next]] = [ids[next], ids[index]];
    void reorderHabits(ids);
  };

  const dropOn = (targetId: number) => {
    if (dragId === null || dragId === targetId) return;
    const ids = habits.map((habit) => habit.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    ids.splice(from, 1);
    ids.splice(to, 0, dragId);
    setDragId(null);
    void reorderHabits(ids);
  };

  const submitHabit = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newHabit.trim();
    if (!name) return;
    try {
      await addHabit(name);
      setNewHabit("");
    } catch {
      // handled by the store
    }
  };

  const archive = async (id: number) => {
    if (habits.length <= 1) {
      toast("Keep at least one active habit.", "error");
      return;
    }
    const habit = habits.find((entry) => entry.id === id);
    if (!habit) return;
    const ok = await confirm(`Archive “${habit.name}”? Its history is kept.`, {
      title: "Archive habit",
      kind: "warning",
    });
    if (ok) await archiveHabit(id);
  };

  const remove = async (id: number) => {
    const habit = archived.find((entry) => entry.id === id);
    if (!habit) return;
    const ok = await confirm(`Permanently delete “${habit.name}” and its history?`, {
      title: "Delete habit",
      kind: "warning",
    });
    if (ok) await deleteHabit(id);
  };

  const saveProfile = async () => {
    try {
      await saveSettings({
        birthDate: birth,
        lifespan: Number(lifespan),
        weekStart,
      });
      toast("Profile saved.", "success");
    } catch (error) {
      toast(errorMessage(error), "error");
    }
  };

  const toggleReminder = async (value: boolean) => {
    if (value) {
      let granted = await isPermissionGranted().catch(() => false);
      if (!granted) {
        const result = await requestPermission().catch(() => "denied");
        granted = result === "granted";
      }
      if (!granted) {
        toast("Notifications are blocked in Windows settings.", "error");
        return;
      }
    }
    try {
      await saveSettings({ reminderEnabled: value });
    } catch (error) {
      toast(errorMessage(error), "error");
    }
  };

  const toggleAutostart = async (value: boolean) => {
    try {
      if (value) await enableAutostart();
      else await disableAutostart();
      setLaunchAtLogin(value);
      await saveSettings({ launchAtLogin: value });
    } catch {
      toast("Launch at login is available in an installed build.", "error");
    }
  };

  const doExport = async () => {
    const path = await save({
      title: "Export span data",
      defaultPath: `span-backup-${todayISO()}.json`,
      filters: [{ name: "span backup", extensions: ["json"] }],
    });
    if (!path) return;
    setBusy(true);
    try {
      await api.exportTo(path);
      toast("Backup exported.", "success");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const doImport = async () => {
    const path = await open({
      title: "Import span data",
      multiple: false,
      filters: [{ name: "span backup", extensions: ["json"] }],
    });
    if (!path || typeof path !== "string") return;
    const ok = await confirm("Replace everything with this backup?", {
      title: "Import backup",
      kind: "warning",
    });
    if (!ok) return;
    setBusy(true);
    try {
      const result = await api.importFrom(path);
      await reload();
      toast(
        `Imported ${result.habits} habits and ${result.completions} check-ins.`,
        "success",
      );
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const doBackup = async () => {
    setBusy(true);
    try {
      const path = await api.backupNow();
      toast(`Backup saved to ${path}`, "success");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const doImportLegacy = async () => {
    const ok = await confirm(
      "Import habits and check-ins from the original span database? This replaces the current data.",
      { title: "Import original span data", kind: "warning" },
    );
    if (!ok) return;
    setBusy(true);
    try {
      const imported = await api.importLegacy();
      if (imported) {
        await reload();
        toast("Original span data imported.", "success");
      } else {
        toast("No original span data was found.", "info");
      }
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const copyDir = async () => {
    try {
      await navigator.clipboard.writeText(dataDir);
      toast("Data folder copied.", "info");
    } catch {
      toast(dataDir, "info");
    }
  };

  return (
    <div className="page settings-page">
      <header className="page-head">
        <div className="page-head__titles">
          <span className="eyebrow">Customize span</span>
          <h1>Preferences</h1>
          <p className="page-head__sub">Everything stays on this device.</p>
        </div>
      </header>

      <div className="settings-grid">
        <section className="panel settings-card">
          <h2>Appearance</h2>
          <p className="settings-help">Choose the energy of the interface and heatmaps.</p>
          <ThemePicker value={settings.theme} onChange={pickTheme} />
          <div className="settings-row">
            <div>
              <strong>Reduce motion</strong>
              <span>Keep transitions minimal and immediate.</span>
            </div>
            <Toggle
              checked={settings.reduceMotion}
              onChange={(value) =>
                void saveSettings({ reduceMotion: value }).catch((error) =>
                  toast(errorMessage(error), "error"),
                )
              }
              label="Reduce motion"
            />
          </div>
        </section>

        <section className="panel settings-card settings-card--wide">
          <div className="settings-card__head">
            <div>
              <h2>Daily habits</h2>
              <p className="settings-help">
                Rename, reorder, or archive. Archived habits keep their history.
              </p>
            </div>
            <span className="count-pill">
              {habits.length} / {MAX_HABITS}
            </span>
          </div>

          <div className="edit-habits">
            {habits.map((habit, index) => (
              <div
                key={habit.id}
                className={`edit-habit ${dragId === habit.id ? "is-dragging" : ""}`}
                onDragEnter={(event) => {
                  if (dragId !== null) event.preventDefault();
                }}
                onDragOver={(event) => {
                  if (dragId === null) return;
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  dropOn(habit.id);
                }}
              >
                <span
                  className="edit-habit__grip"
                  draggable
                  onDragStart={(event) => {
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", String(habit.id));
                    setDragId(habit.id);
                  }}
                  onDragEnd={() => setDragId(null)}
                  title="Drag to reorder"
                >
                  <GripVertical size={14} />
                </span>
                <input
                  value={drafts[habit.id] ?? habit.name}
                  maxLength={80}
                  onChange={(event) =>
                    setDrafts((current) => ({ ...current, [habit.id]: event.target.value }))
                  }
                  onBlur={() => void commitName(habit.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                    if (event.key === "Escape") {
                      setDrafts((current) => ({ ...current, [habit.id]: habit.name }));
                      event.currentTarget.blur();
                    }
                  }}
                  aria-label={`Rename ${habit.name}`}
                />
                <div className="edit-habit__actions">
                  <button
                    className="icon-btn"
                    aria-label="Move up"
                    disabled={index === 0}
                    onClick={() => move(habit.id, -1)}
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    className="icon-btn"
                    aria-label="Move down"
                    disabled={index === habits.length - 1}
                    onClick={() => move(habit.id, 1)}
                  >
                    <ArrowDown size={14} />
                  </button>
                  <button
                    className="icon-btn"
                    aria-label={`Archive ${habit.name}`}
                    onClick={() => void archive(habit.id)}
                  >
                    <Archive size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {habits.length < MAX_HABITS ? (
            <form className="add-habit" onSubmit={(event) => void submitHabit(event)}>
              <input
                value={newHabit}
                maxLength={80}
                onChange={(event) => setNewHabit(event.target.value)}
                placeholder="Add a habit…"
                aria-label="New habit name"
              />
              <button className="btn primary small" type="submit" disabled={!newHabit.trim()}>
                <Plus size={14} /> Add
              </button>
            </form>
          ) : (
            <p className="settings-help">Ten is the limit. Archive one to add another.</p>
          )}

          {archived.length ? (
            <div className="archived">
              <h3>Archived</h3>
              {archived.map((habit) => (
                <div key={habit.id} className="archived__row">
                  <span>{habit.name}</span>
                  <div>
                    <button
                      className="btn ghost small"
                      onClick={() => void restoreHabit(habit.id)}
                    >
                      <RotateCcw size={13} /> Restore
                    </button>
                    <button
                      className="icon-btn danger"
                      aria-label={`Delete ${habit.name}`}
                      onClick={() => void remove(habit.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="panel settings-card">
          <h2>Profile</h2>
          <p className="settings-help">Used to draw your projected span and weeks.</p>
          <label className="field">
            <span>Birth date</span>
            <input type="date" value={birth} max={todayISO()} onChange={(event) => setBirth(event.target.value)} />
          </label>
          <label className="field">
            <span>Expected age</span>
            <input
              type="number"
              min={1}
              max={150}
              value={lifespan}
              onChange={(event) => setLifespan(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Week starts on</span>
            <select
              value={weekStart}
              onChange={(event) => setWeekStart(Number(event.target.value) === 0 ? 0 : 1)}
            >
              <option value={1}>Monday</option>
              <option value={0}>Sunday</option>
            </select>
          </label>
          <button className="btn primary small" onClick={() => void saveProfile()}>
            <Check size={14} /> Save profile
          </button>
        </section>

        <section className="panel settings-card">
          <h2>Reminders & startup</h2>
          <div className="settings-row">
            <div>
              <strong>
                <Bell size={14} /> Daily reminder
              </strong>
              <span>A nudge at the time below if the day is incomplete.</span>
            </div>
            <Toggle
              checked={settings.reminderEnabled}
              onChange={(value) => void toggleReminder(value)}
              label="Daily reminder"
            />
          </div>
          <label className="field field--inline">
            <span>Reminder time</span>
            <input
              type="time"
              value={settings.reminderTime}
              disabled={!settings.reminderEnabled}
              onChange={(event) =>
                void saveSettings({ reminderTime: event.target.value }).catch((error) =>
                  toast(errorMessage(error), "error"),
                )
              }
            />
          </label>
          <div className="settings-row">
            <div>
              <strong>
                <Power size={14} /> Launch at login
              </strong>
              <span>Open span automatically when Windows starts.</span>
            </div>
            <Toggle
              checked={launchAtLogin}
              onChange={(value) => void toggleAutostart(value)}
              label="Launch at login"
            />
          </div>
          <div className="settings-row">
            <div>
              <strong>Minimize to tray</strong>
              <span>Closing the window keeps the reminder running.</span>
            </div>
            <Toggle
              checked={settings.minimizeToTray}
              onChange={(value) =>
                void saveSettings({ minimizeToTray: value }).catch((error) =>
                  toast(errorMessage(error), "error"),
                )
              }
              label="Minimize to tray"
            />
          </div>
        </section>

        <section className="panel settings-card settings-card--wide">
          <div className="settings-card__head">
            <div>
              <h2>Data</h2>
              <p className="settings-help">
                Exports are plain JSON. Automatic daily backups are kept for two weeks.
              </p>
            </div>
            <Database size={18} className="muted-icon" />
          </div>

          <div className="data-actions">
            <button className="btn ghost" disabled={busy} onClick={() => void doExport()}>
              <Download size={15} /> Export backup
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => void doImport()}>
              <Upload size={15} /> Import backup
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => void doBackup()}>
              <HardDriveDownload size={15} /> Backup now
            </button>
            {legacyAvailable ? (
              <button className="btn ghost" disabled={busy} onClick={() => void doImportLegacy()}>
                <Database size={15} /> Import original span data
              </button>
            ) : null}
          </div>

          <div className="data-path">
            <span>{dataDir}</span>
            <button className="icon-btn" aria-label="Copy data folder" onClick={() => void copyDir()}>
              <Copy size={13} />
            </button>
          </div>
        </section>

        <section className="panel settings-card settings-card--wide about">
          <div>
            <h2>span 0.1.0</h2>
            <p className="settings-help">
              A habit tracker. No account, no cloud, no telemetry. Built with Tauri,
              React, and SQLite.
            </p>
          </div>
          <span className="about__badge">Local first</span>
        </section>
      </div>
    </div>
  );
}
