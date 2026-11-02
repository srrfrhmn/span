import { addMonths, format, isAfter, isSameMonth, subMonths } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { iso, monthBounds, monthMatrix, parse, weekdayLabels } from "../lib/dates";
import { heatLevel } from "../lib/heat";
import { api, type DaySummary, type Stats } from "../lib/ipc";
import { useApp } from "../state/store";

export function MonthView() {
  const selectedDay = useApp((state) => state.selectedDay);
  const today = useApp((state) => state.today);
  const settings = useApp((state) => state.settings);
  const habits = useApp((state) => state.habits);
  const selectDay = useApp((state) => state.selectDay);
  const dataVersion = useApp((state) => state.dataVersion);

  const [cursor, setCursor] = useState(() => parse(selectedDay));
  const [summary, setSummary] = useState<DaySummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const next = parse(selectedDay);
    setCursor((current) => (isSameMonth(current, next) ? current : next));
  }, [selectedDay]);

  const bounds = useMemo(
    () => monthBounds(cursor, settings.weekStart),
    [cursor, settings.weekStart],
  );
  const grid = useMemo(
    () => monthMatrix(cursor, settings.weekStart),
    [cursor, settings.weekStart],
  );
  const monthStart = iso(new Date(cursor.getFullYear(), cursor.getMonth(), 1));
  const monthEnd = iso(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0));

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.rangeSummary(bounds.start, bounds.end),
      api.stats(monthStart, monthEnd),
    ])
      .then(([days, aggregate]) => {
        if (!alive) return;
        setSummary(days);
        setStats(aggregate);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [bounds.start, bounds.end, monthStart, monthEnd, dataVersion]);

  const byDay = useMemo(
    () => new Map(summary.map((entry) => [entry.day, entry])),
    [summary],
  );

  const todayDate = parse(today);
  const labels = weekdayLabels(settings.weekStart);

  return (
    <div className="page">
      <header className="page-head">
        <div className="page-head__titles">
          <span className="eyebrow">Month</span>
          <h1>{format(cursor, "MMMM")}</h1>
          <p className="page-head__sub">{format(cursor, "yyyy")}</p>
        </div>
        <div className="page-head__actions">
          <div className="day-nav">
            <button className="icon-btn" aria-label="Previous month" onClick={() => setCursor((c) => subMonths(c, 1))}>
              <ChevronLeft size={17} />
            </button>
            <button className="icon-btn" aria-label="Next month" onClick={() => setCursor((c) => addMonths(c, 1))}>
              <ChevronRight size={17} />
            </button>
            <button
              className="btn ghost small"
              onClick={() => {
                const now = parse(today);
                setCursor(now);
                void selectDay(today);
              }}
            >
              This month
            </button>
          </div>
        </div>
      </header>

      <div className="month-layout">
        <section className="panel calendar-panel">
          <div className="calendar">
            <div className="calendar__weekdays">
              {labels.map((label, index) => (
                <span key={`${label}-${index}`}>{label}</span>
              ))}
            </div>
            <div className="calendar__grid">
              {grid.map((day) => {
                const key = iso(day);
                const entry = byDay.get(key);
                const localTarget = entry?.target ?? habits.length;
                const heat = heatLevel(entry?.count ?? 0, localTarget);
                const outside = !isSameMonth(day, cursor);
                const future = isAfter(day, todayDate);
                return (
                  <button
                    key={key}
                    className={[
                      "day-cell",
                      `heat-${heat}`,
                      outside ? "is-outside" : "",
                      future ? "is-future" : "",
                      key === today ? "is-today" : "",
                      key === selectedDay ? "is-selected" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    disabled={future}
                    onClick={() => void selectDay(key)}
                    aria-label={format(day, "EEEE, MMMM d, yyyy")}
                  >
                    <span className="day-cell__num">{format(day, "d")}</span>
                    {entry && entry.count > 0 && !outside ? (
                      <span className="day-cell__count">
                        {entry.count}
                        <em>/{localTarget}</em>
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="legend">
            <span>Less</span>
            {[0, 1, 2, 3, 4, 5].map((step) => (
              <i key={step} className={`legend__cell heat-${step}`} />
            ))}
            <span>More</span>
          </div>
        </section>

        <aside className="month-side">
          <section className="panel stat-panel">
            <h2>This month</h2>
            <div className="big-stat">
              <strong>{Math.round((stats?.rate ?? 0) * 100)}%</strong>
              <span>completion</span>
            </div>
            <div className="meter">
              <i style={{ width: `${Math.round((stats?.rate ?? 0) * 100)}%` }} />
            </div>
            <dl className="stat-list">
              <div>
                <dt>Perfect days</dt>
                <dd>{stats?.perfectDays ?? 0}</dd>
              </div>
              <div>
                <dt>Active days</dt>
                <dd>{stats?.activeDays ?? 0}</dd>
              </div>
              <div>
                <dt>Best streak</dt>
                <dd>{stats?.bestStreak ?? 0}</dd>
              </div>
            </dl>
          </section>

          <section className="panel">
            <h2>Habit consistency</h2>
            <ul className="consistency">
              {(stats?.perHabit ?? []).map((habit) => (
                <li key={habit.habitId}>
                  <span>{habit.name}</span>
                  <span className="consistency__bar">
                    <i style={{ width: `${Math.round(habit.rate * 100)}%` }} />
                  </span>
                  <em>{Math.round(habit.rate * 100)}%</em>
                </li>
              ))}
              {!stats?.perHabit.length ? <li className="muted">No habits yet.</li> : null}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
