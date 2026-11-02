import { addDays, format } from "date-fns";
import {
  ChevronLeft,
  ChevronRight,
  NotebookPen,
  Plus,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { HabitRow } from "../components/HabitRow";
import { Ring } from "../components/Ring";
import { iso, lastSevenDays, longDate, parse } from "../lib/dates";
import { api, type DaySummary, type HabitMark, type Stats } from "../lib/ipc";
import { useApp } from "../state/store";

export function TodayView() {
  const day = useApp((state) => state.day);
  const habits = useApp((state) => state.habits);
  const selectedDay = useApp((state) => state.selectedDay);
  const today = useApp((state) => state.today);
  const selectDay = useApp((state) => state.selectDay);
  const toggle = useApp((state) => state.toggle);
  const addHabit = useApp((state) => state.addHabit);
  const saveNote = useApp((state) => state.setNote);
  const dataVersion = useApp((state) => state.dataVersion);

  const [marks, setMarks] = useState<HabitMark[]>([]);
  const [weekSummary, setWeekSummary] = useState<DaySummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [note, setNoteDraft] = useState(day?.note ?? "");
  const [noteState, setNoteState] = useState<"saved" | "saving">("saved");
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");

  const selected = parse(selectedDay);
  const isToday = selectedDay === today;
  const completed = day?.completed.length ?? 0;
  const target = day?.target ?? 0;
  const ratio = target > 0 ? Math.min(1, completed / target) : 0;
  const perfect = target > 0 && completed >= target;

  useEffect(() => {
    let alive = true;
    const end = parse(selectedDay);
    api
      .completionsRange(iso(addDays(end, -399)), selectedDay)
      .then((rows) => {
        if (alive) setMarks(rows);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [selectedDay, dataVersion]);

  useEffect(() => {
    let alive = true;
    const end = parse(today);
    Promise.all([
      api.rangeSummary(iso(addDays(end, -6)), today),
      api.stats(iso(addDays(end, -29)), today),
    ])
      .then(([week, month]) => {
        if (!alive) return;
        setWeekSummary(week);
        setStats(month);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [today, dataVersion]);

  useEffect(() => {
    setNoteDraft(day?.note ?? "");
    setNoteState("saved");
  }, [selectedDay, day?.note]);

  useEffect(() => {
    if (note === (day?.note ?? "")) return;
    setNoteState("saving");
    const handle = window.setTimeout(() => {
      void saveNote(note).then(() => setNoteState("saved"));
    }, 650);
    return () => window.clearTimeout(handle);
  }, [note, day?.note, saveNote]);

  const marksByHabit = useMemo(() => {
    const map = new Map<number, Set<string>>();
    for (const mark of marks) {
      const set = map.get(mark.habitId) ?? new Set<string>();
      set.add(mark.day);
      map.set(mark.habitId, set);
    }
    return map;
  }, [marks]);

  const habitStreaks = useMemo(() => {
    const result: Record<number, number> = {};
    for (const habit of habits) {
      const set = marksByHabit.get(habit.id);
      if (!set) {
        result[habit.id] = 0;
        continue;
      }
      let cursor = parse(selectedDay);
      if (!set.has(iso(cursor))) cursor = addDays(cursor, -1);
      let count = 0;
      while (set.has(iso(cursor)) && count < 400) {
        count += 1;
        cursor = addDays(cursor, -1);
      }
      result[habit.id] = count;
    }
    return result;
  }, [habits, marksByHabit, selectedDay]);

  const week = useMemo(() => lastSevenDays(parse(selectedDay)), [selectedDay]);
  const weekMap = useMemo(
    () => new Map(weekSummary.map((entry) => [entry.day, entry])),
    [weekSummary],
  );
  const currentWeek = useMemo(() => lastSevenDays(parse(today)), [today]);

  const shiftDay = (offset: number) => {
    void selectDay(iso(addDays(selected, offset)));
  };

  const submitHabit = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    try {
      await addHabit(name);
      setNewName("");
      setAdding(false);
    } catch {
      // the store surfaces the error
    }
  };

  return (
    <div className="page today-page">
      <header className="page-head">
        <div className="page-head__titles">
          <span className="eyebrow">Daily check-in</span>
          <h1>{isToday ? "Today" : format(selected, "EEEE")}</h1>
          <p className="page-head__sub">{longDate(selectedDay)}</p>
        </div>

        <div className="page-head__actions">
          <div className="day-nav">
            <button className="icon-btn" aria-label="Previous day" onClick={() => shiftDay(-1)}>
              <ChevronLeft size={17} />
            </button>
            <button className="icon-btn" aria-label="Next day" onClick={() => shiftDay(1)} disabled={selectedDay >= today}>
              <ChevronRight size={17} />
            </button>
            {!isToday ? (
              <button className="btn ghost small" onClick={() => void selectDay(today)}>
                Back to today
              </button>
            ) : null}
          </div>
          <div className="today-progress">
            <Ring value={ratio} label={`${completed} of ${target} habits complete`} />
            <div>
              <strong>
                {completed}
                <span> / {target}</span>
              </strong>
              <small>{perfect ? "Perfect day" : target ? `${target - completed} to go` : "No habits yet"}</small>
            </div>
          </div>
        </div>
      </header>

      <div className="today-grid">
        <section className="panel habits-panel">
          <div className="panel__head">
            <div>
              <h2>Daily habits</h2>
              <p>{habits.length ? `${completed} of ${target} kept` : "Add the promises you want to keep"}</p>
            </div>
            {habits.length < 10 ? (
              <button className="btn ghost small" onClick={() => setAdding(true)}>
                <Plus size={14} /> Add habit
              </button>
            ) : null}
          </div>

          {perfect ? (
            <div className="perfect-banner">
              <Sparkles size={16} />
              <span>Every promise kept. That is a perfect day.</span>
            </div>
          ) : null}

          <div className="habit-list">
            {habits.map((habit) => (
              <HabitRow
                key={habit.id}
                habit={habit}
                done={day?.completed.includes(habit.id) ?? false}
                streak={habitStreaks[habit.id] ?? 0}
                week={week.map((entry) => ({
                  day: iso(entry),
                  label: format(entry, "EEE, MMM d"),
                  done: marksByHabit.get(habit.id)?.has(iso(entry)) ?? false,
                }))}
                onToggle={() => void toggle(habit.id)}
              />
            ))}

            {habits.length === 0 ? (
              <div className="empty-state">
                <p>No habits yet.</p>
                <button className="btn primary small" onClick={() => setAdding(true)}>
                  <Plus size={14} /> Add your first habit
                </button>
              </div>
            ) : null}
          </div>

          {adding ? (
            <form className="add-habit" onSubmit={(event) => void submitHabit(event)}>
              <input
                autoFocus
                value={newName}
                maxLength={80}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="Name a habit…"
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setAdding(false);
                    setNewName("");
                  }
                }}
              />
              <button className="btn primary small" type="submit" disabled={!newName.trim()}>
                Add
              </button>
              <button
                type="button"
                className="btn ghost small"
                onClick={() => {
                  setAdding(false);
                  setNewName("");
                }}
              >
                Cancel
              </button>
            </form>
          ) : null}
        </section>

        <div className="today-side">
          <section className="panel week-panel">
            <div className="panel__head">
              <div>
                <h2>This week</h2>
                <p>Tap a day to review it</p>
              </div>
            </div>
            <div className="week-strip">
              {currentWeek.map((entry) => {
                const key = iso(entry);
                const summary = weekMap.get(key);
                const localTarget = summary?.target ?? habits.length;
                const level =
                  localTarget > 0 && summary ? Math.min(1, summary.count / localTarget) : 0;
                return (
                  <button
                    key={key}
                    className={`week-day ${key === selectedDay ? "is-selected" : ""} ${key === today ? "is-today" : ""}`}
                    onClick={() => void selectDay(key)}
                    aria-label={format(entry, "EEEE, MMMM d")}
                  >
                    <span className="week-day__label">{format(entry, "EEEEE")}</span>
                    <span className="week-day__num">{format(entry, "d")}</span>
                    <span className="week-day__bar">
                      <i style={{ height: `${Math.max(8, level * 100)}%` }} />
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="panel momentum-panel">
            <div className="panel__head">
              <div>
                <h2>Last 30 days</h2>
                <p>How the month is going</p>
              </div>
              <span className="momentum-panel__icon">
                <TrendingUp size={16} />
              </span>
            </div>
            <div className="momentum">
              <strong>{Math.round((stats?.rate ?? 0) * 100)}%</strong>
              <span>completion</span>
              <div className="meter">
                <i style={{ width: `${Math.round((stats?.rate ?? 0) * 100)}%` }} />
              </div>
            </div>
            <div className="mini-stats">
              <div>
                <strong>{stats?.perfectDays ?? 0}</strong>
                <span>perfect days</span>
              </div>
              <div>
                <strong>{stats?.bestStreak ?? 0}</strong>
                <span>best streak</span>
              </div>
            </div>
          </section>

          <section className="panel note-panel">
            <div className="panel__head">
              <div>
                <h2>
                  <NotebookPen size={15} /> Daily note
                </h2>
                <p>Private, stored on this device</p>
              </div>
              <span className={`note-state ${noteState === "saving" ? "is-saving" : ""}`}>
                {noteState === "saving" ? "Saving…" : "Saved"}
              </span>
            </div>
            <textarea
              className="note-input"
              value={note}
              maxLength={5000}
              placeholder="A line about the day…"
              onChange={(event) => setNoteDraft(event.target.value)}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
