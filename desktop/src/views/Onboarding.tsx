import { format, subYears } from "date-fns";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Database,
  Flame,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { ThemePicker } from "../components/ThemePicker";
import { api, type ThemeKey } from "../lib/ipc";
import { iso, todayISO } from "../lib/dates";

import { errorMessage, useApp } from "../state/store";

const STARTERS = [
  "Move for 20 minutes",
  "Read 10 pages",
  "Drink water",
  "Write a line",
  "Sleep by 11 PM",
  "No phone after waking",
];

const STEPS = ["Welcome", "Data", "Theme", "Habits", "Profile"] as const;

export function Onboarding() {
  const settings = useApp((state) => state.settings);
  const legacyAvailable = useApp((state) => state.legacyAvailable);
  const saveSettings = useApp((state) => state.saveSettings);
  const addHabit = useApp((state) => state.addHabit);
  const reload = useApp((state) => state.reload);
  const toast = useApp((state) => state.toast);

  const [step, setStep] = useState(0);
  const [theme, setTheme] = useState<ThemeKey>(settings.theme);
  const [chosen, setChosen] = useState<string[]>(["Move for 20 minutes", "Read 10 pages"]);
  const [birth, setBirth] = useState(settings.birthDate);
  const [lifespan, setLifespan] = useState(String(settings.lifespan));
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(false);

  const maxYear = todayISO();

  const previewTheme = (key: ThemeKey) => {
    setTheme(key);
    document.documentElement.dataset.theme = key;
    document.documentElement.style.colorScheme = key === "paper" ? "light" : "dark";
  };

  const importLegacy = async () => {
    setImporting(true);
    try {
      const imported = await api.importLegacy();
      if (imported) {
        setImported(true);
        toast("Original span data imported.", "success");
        setStep(2);
      } else {
        toast("No original span data was found.", "info");
      }
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setImporting(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      let added = 0;
      if (!imported) {
        for (const name of chosen) {
          await addHabit(name);
          added += 1;
        }
      }
      await saveSettings({
        theme,
        birthDate: birth,
        lifespan: Number(lifespan) || settings.lifespan,
        onboarded: true,
      });
      await reload();
      toast("Setup complete.", "success");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const toggleStarter = (name: string) => {
    setChosen((current) =>
      current.includes(name)
        ? current.filter((entry) => entry !== name)
        : [...current, name].slice(0, 10),
    );
  };

  const next = () =>
    setStep((value) => {
      const skip = imported && value === 2 ? 4 : value + 1;
      return Math.min(STEPS.length - 1, skip);
    });
  const back = () =>
    setStep((value) => Math.max(0, imported && value === 4 ? 2 : value - 1));

  return (
    <div className="onboarding">
      <div className="onboarding__glow" aria-hidden />
      <div className="onboarding__card">
        <header className="onboarding__head">
          <div className="onboarding__brand">
            <span className="mark">s</span>
            <span>span</span>
          </div>
          <ol className="onboarding__steps" aria-label="Setup progress">
            {STEPS.map((label, index) => (
              <li
                key={label}
                className={`${index === step ? "is-active" : ""} ${index < step ? "is-done" : ""}`}
              >
                <i>{index < step ? <Check size={9} /> : index + 1}</i>
                <span>{label}</span>
              </li>
            ))}
          </ol>
        </header>

        <div className="onboarding__body">
          {step === 0 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">A habit tracker</span>
              <h1>Track your daily habits.</h1>
              <p className="onboarding__lede">
                Mark each habit when you complete it. All data stays on this device. There
                is no account and no cloud sync.
              </p>
              <ul className="onboarding__points">
                <li>
                  <Flame size={16} />
                  <span>
                    <strong>Check in each day</strong>
                    <em>Tap a habit to mark it complete.</em>
                  </span>
                </li>
                <li>
                  <Sparkles size={16} />
                  <span>
                    <strong>See your history</strong>
                    <em>The Month, Year, and Life views show your progress.</em>
                  </span>
                </li>
                <li>
                  <Database size={16} />
                  <span>
                    <strong>Local data</strong>
                    <em>span stores data in SQLite. You can export it as JSON.</em>
                  </span>
                </li>
              </ul>
            </section>
          ) : null}

          {step === 1 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Data</span>
              <h1>{legacyAvailable ? "Import your history." : "New database."}</h1>
              <p className="onboarding__lede">
                {legacyAvailable
                  ? "A database from the original span app is on this computer. Import it to keep your habits and check-ins."
                  : "There is no database from the original span app on this computer. You can import a JSON backup later in Settings."}
              </p>
              {legacyAvailable ? (
                <button
                  className="btn primary"
                  disabled={importing}
                  onClick={() => void importLegacy()}
                >
                  <Database size={15} />
                  {importing ? "Importing…" : "Import history"}
                </button>
              ) : (
                <div className="onboarding__note">
                  <Check size={14} />
                  <span>span will make a new database.</span>
                </div>
              )}
              <p className="onboarding__fine">
                span keeps new data in a separate file. The original app continues to work.
              </p>
            </section>
          ) : null}

          {step === 2 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Theme</span>
              <h1>Select a theme.</h1>
              <p className="onboarding__lede">
                There are five dark themes and one light theme. You can change the theme
                later in Settings.
              </p>
              <ThemePicker value={theme} onChange={previewTheme} />
            </section>
          ) : null}

          {step === 3 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Habits</span>
              <h1>Select your habits.</h1>
              <p className="onboarding__lede">
                Select some habits to start. You can have a maximum of 10 active habits. You
                can add, rename, or archive habits later.
              </p>
              <div className="starter-grid">
                {STARTERS.map((name) => {
                  const active = chosen.includes(name);
                  return (
                    <button
                      key={name}
                      className={`starter ${active ? "is-chosen" : ""}`}
                      onClick={() => toggleStarter(name)}
                      aria-pressed={active}
                    >
                      <span className="starter__check">
                        <Check size={12} />
                      </span>
                      {name}
                    </button>
                  );
                })}
              </div>
              <p className="onboarding__fine">
                {chosen.length === 0
                  ? "No habits selected. You can add habits on the Today page."
                  : `${chosen.length} selected.`}
              </p>
            </section>
          ) : null}

          {step === 4 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Profile</span>
              <h1>Enter your profile.</h1>
              <p className="onboarding__lede">
                The Life view uses your birth date and expected age to show your life in
                weeks. This data stays on this device.
              </p>
              <div className="onboarding__fields">
                <label className="field">
                  <span>Birth date</span>
                  <input
                    type="date"
                    value={birth}
                    max={maxYear}
                    min={iso(subYears(new Date(), 120))}
                    onChange={(event) => setBirth(event.target.value)}
                  />
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
              </div>
              <div className="onboarding__summary">
                <span>Start date</span>
                <strong>{format(new Date(), "MMMM d, yyyy")}</strong>
              </div>
            </section>
          ) : null}
        </div>

        <footer className="onboarding__foot">
          <button
            className="btn ghost"
            onClick={back}
            disabled={step === 0 || busy}
            style={{ visibility: step === 0 ? "hidden" : "visible" }}
          >
            <ArrowLeft size={15} /> Back
          </button>
          <span className="onboarding__counter">
            {step + 1} / {STEPS.length}
          </span>
          {step < STEPS.length - 1 ? (
            <button className="btn primary" onClick={next}>
              Next <ArrowRight size={15} />
            </button>
          ) : (
            <button className="btn primary" onClick={() => void finish()} disabled={busy}>
              <Check size={15} />
              {busy ? "Saving…" : "Start"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
