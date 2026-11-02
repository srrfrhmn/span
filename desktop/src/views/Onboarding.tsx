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
  "Sleep by 11",
  "No phone on waking",
];

const STEPS = ["Welcome", "Your data", "Look", "Habits", "You"] as const;

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
        toast("Your original span data is here.", "success");
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
      toast(
        added > 0 ? "You are set. Keep one promise today." : "You are set.",
        "success",
      );
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
              <h1>Small promises, kept daily.</h1>
              <p className="onboarding__lede">
                span is a gentle place to check in on the habits that matter. No streaks to
                chase beyond your own, no account, no cloud. Everything lives on this
                device.
              </p>
              <ul className="onboarding__points">
                <li>
                  <Flame size={16} />
                  <span>
                    <strong>One tap a day</strong>
                    <em>Mark what you kept, and see the month fill in.</em>
                  </span>
                </li>
                <li>
                  <Sparkles size={16} />
                  <span>
                    <strong>Notice the pattern</strong>
                    <em>Month, year, and lifetime heatmaps make momentum visible.</em>
                  </span>
                </li>
                <li>
                  <Database size={16} />
                  <span>
                    <strong>Yours to keep</strong>
                    <em>Plain SQLite on disk, with one-click JSON backups.</em>
                  </span>
                </li>
              </ul>
            </section>
          ) : null}

          {step === 1 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Your data</span>
              <h1>{legacyAvailable ? "Bring your history along." : "Start fresh."}</h1>
              <p className="onboarding__lede">
                {legacyAvailable
                  ? "The original span app left a database on this machine. Import it once and every habit and check-in carries over."
                  : "There is no older span database on this machine. You can import a JSON backup later from Preferences."}
              </p>
              {legacyAvailable ? (
                <button
                  className="btn primary"
                  disabled={importing}
                  onClick={() => void importLegacy()}
                >
                  <Database size={15} />
                  {importing ? "Importing…" : "Import my span history"}
                </button>
              ) : (
                <div className="onboarding__note">
                  <Check size={14} />
                  <span>Nothing to import — we will set up a clean database.</span>
                </div>
              )}
              <p className="onboarding__fine">
                Your new data is stored separately, so the original app keeps working.
              </p>
            </section>
          ) : null}

          {step === 2 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">The look</span>
              <h1>Pick a mood.</h1>
              <p className="onboarding__lede">
                Five dark themes and one light. You can change this at any time in
                Preferences.
              </p>
              <ThemePicker value={theme} onChange={previewTheme} />
            </section>
          ) : null}

          {step === 3 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">Your habits</span>
              <h1>What will you keep?</h1>
              <p className="onboarding__lede">
                Choose a few to begin. Keep it small — you can add up to ten later, and
                archive anything that stops serving you.
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
                  ? "No habits selected — you can add them on the Today screen."
                  : `${chosen.length} selected.`}
              </p>
            </section>
          ) : null}

          {step === 4 ? (
            <section className="onboarding__panel">
              <span className="eyebrow">You</span>
              <h1>One last thing.</h1>
              <p className="onboarding__lede">
                The Life view draws your weeks. It only needs a birth date and an expected
                age, and it never leaves this machine.
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
                <span>Starting from</span>
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
              Continue <ArrowRight size={15} />
            </button>
          ) : (
            <button className="btn primary" onClick={() => void finish()} disabled={busy}>
              <Check size={15} />
              {busy ? "Setting up…" : "Begin"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
