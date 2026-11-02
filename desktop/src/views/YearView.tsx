import { format, isAfter } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { iso, monthMatrix, parse, weekdayLabels, yearBounds } from "../lib/dates";
import { heatLevel } from "../lib/heat";
import { api, type DaySummary, type Stats } from "../lib/ipc";
import { useApp } from "../state/store";

interface MiniMonthProps {
  month: Date;
  weekStart: 0 | 1;
  byDay: Map<string, DaySummary>;
  habits: number;
  today: string;
  selected: string;
  onPick: (day: string) => void;
}

function MiniMonth({ month, weekStart, byDay, habits, today, selected, onPick }: MiniMonthProps) {
  const grid = monthMatrix(month, weekStart);
  const labels = weekdayLabels(weekStart);
  const monthIndex = month.getMonth();
  return (
    <section className="mini-month">
      <header>
        <h3>{format(month, "MMMM")}</h3>
      </header>
      <div className="mini-month__labels">
        {labels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      <div className="mini-month__grid">
        {grid.map((day) => {
          if (day.getMonth() !== monthIndex) {
            return <span key={iso(day)} className="mini-cell is-outside" />;
          }
          const key = iso(day);
          const entry = byDay.get(key);
          const target = entry?.target ?? habits;
          const heat = heatLevel(entry?.count ?? 0, target);
          return (
            <button
              key={key}
              className={`mini-cell heat-${heat} ${key === today ? "is-today" : ""} ${key === selected ? "is-selected" : ""} ${isAfter(day, parse(today)) ? "is-future" : ""}`}
              onClick={() => onPick(key)}
              title={format(day, "EEEE, MMMM d")}
              aria-label={format(day, "EEEE, MMMM d, yyyy")}
            />
          );
        })}
      </div>
    </section>
  );
}

export function YearView() {
  const selectedDay = useApp((state) => state.selectedDay);
  const today = useApp((state) => state.today);
  const settings = useApp((state) => state.settings);
  const habits = useApp((state) => state.habits);
  const selectDay = useApp((state) => state.selectDay);
  const dataVersion = useApp((state) => state.dataVersion);

  const [year, setYear] = useState(() => parse(selectedDay).getFullYear());
  const [summary, setSummary] = useState<DaySummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    setYear(parse(selectedDay).getFullYear());
  }, [selectedDay]);

  const bounds = useMemo(() => yearBounds(year), [year]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.rangeSummary(bounds.start, bounds.end), api.stats(bounds.start, bounds.end)])
      .then(([days, aggregate]) => {
        if (!alive) return;
        setSummary(days);
        setStats(aggregate);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [bounds.start, bounds.end, dataVersion]);

  const byDay = useMemo(
    () => new Map(summary.map((entry) => [entry.day, entry])),
    [summary],
  );

  const months = useMemo(
    () => Array.from({ length: 12 }, (_, index) => new Date(year, index, 1)),
    [year],
  );

  return (
    <div className="page">
      <header className="page-head">
        <div className="page-head__titles">
          <span className="eyebrow">Year</span>
          <h1>{year}</h1>
          <p className="page-head__sub">A year at a glance</p>
        </div>
        <div className="page-head__actions">
          <div className="day-nav">
            <button className="icon-btn" aria-label="Previous year" onClick={() => setYear((value) => value - 1)}>
              <ChevronLeft size={17} />
            </button>
            <button className="icon-btn" aria-label="Next year" onClick={() => setYear((value) => value + 1)}>
              <ChevronRight size={17} />
            </button>
            <button
              className="btn ghost small"
              onClick={() => {
                setYear(parse(today).getFullYear());
                void selectDay(today);
              }}
            >
              This year
            </button>
          </div>
        </div>
      </header>

      <div className="year-layout">
        <section className="panel year-panel">
          <div className="year-grid">
            {months.map((month) => (
              <MiniMonth
                key={month.getMonth()}
                month={month}
                weekStart={settings.weekStart}
                byDay={byDay}
                habits={habits.length}
                today={today}
                selected={selectedDay}
                onPick={(day) => void selectDay(day)}
              />
            ))}
          </div>
          <div className="legend">
            <span>Less</span>
            {[0, 1, 2, 3, 4, 5].map((step) => (
              <i key={step} className={`legend__cell heat-${step}`} />
            ))}
            <span>More</span>
          </div>
        </section>

        <aside className="year-side">
          <section className="panel stat-panel">
            <h2>This year</h2>
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
        </aside>
      </div>
    </div>
  );
}
