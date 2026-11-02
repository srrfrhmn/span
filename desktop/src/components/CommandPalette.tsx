import { useMemo, useRef, useState, useEffect, type ReactNode } from "react";
import {
  CalendarDays,
  Grid3x3,
  Hourglass,
  Search,
  Settings,
  Sun,
  ToggleLeft,
} from "lucide-react";
import { format, isValid, parse as parseDate } from "date-fns";
import { useApp } from "../state/store";
import { iso } from "../lib/dates";

interface Item {
  id: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  run: () => void;
}

export function CommandPalette() {
  const close = useApp((state) => state.setPalette);
  const habits = useApp((state) => state.habits);
  const day = useApp((state) => state.day);
  const today = useApp((state) => state.today);
  const setView = useApp((state) => state.setView);
  const selectDay = useApp((state) => state.selectDay);
  const toggle = useApp((state) => state.toggle);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const done = new Set(day?.completed ?? []);

  const go = (view: "today" | "month" | "year" | "life" | "settings") => {
    setView(view);
  };

  const items = useMemo<Item[]>(() => {
    const base: Item[] = [
      {
        id: "today",
        label: "Go to Today",
        hint: "View",
        icon: <Sun size={16} />,
        run: () => {
          setView("today");
          void selectDay(today);
        },
      },
      {
        id: "month",
        label: "Go to Month",
        hint: "View",
        icon: <CalendarDays size={16} />,
        run: () => go("month"),
      },
      {
        id: "year",
        label: "Go to Year",
        hint: "View",
        icon: <Grid3x3 size={16} />,
        run: () => go("year"),
      },
      {
        id: "life",
        label: "Go to Life",
        hint: "View",
        icon: <Hourglass size={16} />,
        run: () => go("life"),
      },
      {
        id: "settings",
        label: "Open Preferences",
        hint: "Settings",
        icon: <Settings size={16} />,
        run: () => go("settings"),
      },
    ];

    for (const habit of habits) {
      base.push({
        id: `habit-${habit.id}`,
        label: `${done.has(habit.id) ? "Uncheck" : "Check"} ${habit.name}`,
        hint: done.has(habit.id) ? "Done today" : "Habit",
        icon: <ToggleLeft size={16} />,
        run: () => {
          setView("today");
          if (day && day.day !== today) {
            void selectDay(today).then(() => void toggle(habit.id));
          } else {
            void toggle(habit.id);
          }
        },
      });
    }

    const parsed = parseDate(query.trim(), "yyyy-MM-dd", new Date());
    if (/^\d{4}-\d{2}-\d{2}$/.test(query.trim()) && isValid(parsed)) {
      base.unshift({
        id: "date",
        label: `Go to ${format(parsed, "EEEE, MMMM d, yyyy")}`,
        hint: "Date",
        icon: <CalendarDays size={16} />,
        run: () => {
          void selectDay(iso(parsed));
        },
      });
    }

    return base;
  }, [habits, done, day, today, query, setView, selectDay, toggle]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(needle) ||
        item.hint?.toLowerCase().includes(needle),
    );
  }, [items, query]);

  useEffect(() => {
    setIndex(0);
  }, [query]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const node = listRef.current?.querySelector(".palette__item.is-selected");
    node?.scrollIntoView({ block: "nearest" });
  }, [index]);

  const run = (item: Item | undefined) => {
    if (!item) return;
    close(false);
    item.run();
  };

  return (
    <div className="palette-backdrop" onMouseDown={() => close(false)}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Quick actions"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="palette__search">
          <Search size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Jump to a day, view, or habit…"
            onKeyDown={(event) => {
              if (event.key === "Escape") close(false);
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setIndex((current) => (current + 1) % Math.max(1, filtered.length));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setIndex(
                  (current) =>
                    (current - 1 + Math.max(1, filtered.length)) %
                    Math.max(1, filtered.length),
                );
              }
              if (event.key === "Enter") run(filtered[index]);
            }}
          />
          <kbd>esc</kbd>
        </div>
        <div className="palette__list" ref={listRef}>
          {filtered.length === 0 ? (
            <p className="palette__empty">No actions match that.</p>
          ) : (
            filtered.map((item, position) => (
              <button
                key={item.id}
                className={`palette__item ${position === index ? "is-selected" : ""}`}
                onMouseEnter={() => setIndex(position)}
                onClick={() => run(item)}
              >
                <span className="palette__icon">{item.icon}</span>
                <span className="palette__label">{item.label}</span>
                {item.hint ? <span className="palette__hint">{item.hint}</span> : null}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
