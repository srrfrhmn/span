use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    sync::{Mutex, MutexGuard},
};

use chrono::{Datelike, Duration, Local, NaiveDate};
use rusqlite::{params, Connection, OpenFlags, OptionalExtension};
use serde_json::{json, Map, Value};

use crate::{
    error::{AppError, Result},
    models::*,
};

pub const MAX_HABITS: i64 = 10;
pub const THEMES: [&str; 6] = ["forest", "ocean", "violet", "ember", "mono", "paper"];

const SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS completions (
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    PRIMARY KEY (habit_id, day)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_targets (
    day TEXT PRIMARY KEY,
    total INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS day_notes (
    day TEXT PRIMARY KEY,
    body TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS completions_day ON completions(day);
CREATE INDEX IF NOT EXISTS completions_habit_day ON completions(habit_id, day);
CREATE INDEX IF NOT EXISTS habits_active ON habits(archived, position);
"#;

pub fn today() -> NaiveDate {
    Local::now().date_naive()
}

pub fn today_iso() -> String {
    iso(today())
}

pub fn iso(day: NaiveDate) -> String {
    day.format("%Y-%m-%d").to_string()
}

pub fn parse_day(value: &str) -> Result<NaiveDate> {
    if value.len() != 10 {
        return Err(AppError::msg("Expected a date in YYYY-MM-DD format"));
    }
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .map_err(|_| AppError::msg("Expected a date in YYYY-MM-DD format"))
}

fn parse_time(value: &str) -> bool {
    let mut parts = value.split(':');
    let (Some(h), Some(m), None) = (parts.next(), parts.next(), parts.next()) else {
        return false;
    };
    matches!((h.parse::<u32>(), m.parse::<u32>()), (Ok(h), Ok(m)) if h < 24 && m < 60)
}

pub fn default_data_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            return PathBuf::from(appdata).join("span");
        }
    }
    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join("Library/Application Support/span");
        }
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if let Ok(data) = std::env::var("XDG_DATA_HOME") {
            return PathBuf::from(data).join("span");
        }
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join(".local/share/span");
        }
    }
    PathBuf::from(".").join("span")
}

fn default_birth(today: NaiveDate) -> String {
    iso(NaiveDate::from_ymd_opt(today.year() - 30, 1, 1).unwrap_or(today))
}

pub struct Db {
    conn: Mutex<Connection>,
    dir: PathBuf,
}

impl Db {
    pub fn open() -> Result<Self> {
        Self::open_at(default_data_dir())
    }

    pub fn open_at(dir: PathBuf) -> Result<Self> {
        fs::create_dir_all(&dir)?;
        let path = dir.join("span-v2.db");
        let conn = Connection::open(&path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA foreign_keys = ON;
             PRAGMA busy_timeout = 5000;",
        )?;
        migrate(&conn)?;
        seed_defaults(&conn)?;
        Ok(Self {
            conn: Mutex::new(conn),
            dir,
        })
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    pub fn legacy_path(&self) -> PathBuf {
        self.dir.join("span.db")
    }

    fn lock(&self) -> Result<MutexGuard<'_, Connection>> {
        self.conn
            .lock()
            .map_err(|_| AppError::msg("The local database is unavailable"))
    }

    pub fn settings(&self) -> Result<Settings> {
        let conn = self.lock()?;
        settings_from(&conn)
    }

    pub fn legacy_available(&self) -> Result<bool> {
        let conn = self.lock()?;
        Ok(self.legacy_path().exists()
            && setting_value(&conn, "legacy_imported_at")?.is_none())
    }

    pub fn active_habits(&self) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        active_habits(&conn)
    }

    pub fn archived_habits(&self) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, name, position, archived FROM habits WHERE archived = 1 ORDER BY position, id",
        )?;
        let rows = stmt.query_map([], habit_from_row)?;
        Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
    }

    pub fn streak(&self, through: Option<&str>) -> Result<Streak> {
        let through = match through {
            Some(value) => parse_day(value)?,
            None => today(),
        };
        let conn = self.lock()?;
        let active = active_count(&conn)?;
        streaks(&conn, through, active)
    }

    pub fn day_state(&self, day: &str) -> Result<DayState> {
        let parsed = parse_day(day)?;
        let conn = self.lock()?;
        let habits = active_habits(&conn)?;
        let target = target_for(&conn, day)?.unwrap_or(habits.len() as i64);
        let completed = completed_ids(&conn, day)?;
        let note = note_for(&conn, day)?;
        let streak = current_streak(&conn, today(), habits.len() as i64)?;
        let _ = parsed;
        Ok(DayState {
            day: day.to_string(),
            habits,
            completed,
            target,
            note,
            streak,
        })
    }

    pub fn toggle(&self, habit_id: i64, day: &str) -> Result<DayState> {
        let parsed = parse_day(day)?;
        if parsed > today() {
            return Err(AppError::msg("Future days cannot be edited"));
        }
        {
            let conn = self.lock()?;
            let archived: Option<i64> = conn
                .query_row(
                    "SELECT archived FROM habits WHERE id = ?1",
                    params![habit_id],
                    |row| row.get(0),
                )
                .optional()?;
            match archived {
                None => return Err(AppError::msg("That habit no longer exists")),
                Some(1) => return Err(AppError::msg("Archived habits cannot be edited")),
                _ => {}
            }
            let exists: bool = conn.query_row(
                "SELECT EXISTS(SELECT 1 FROM completions WHERE habit_id = ?1 AND day = ?2)",
                params![habit_id, day],
                |row| row.get(0),
            )?;
            if exists {
                conn.execute(
                    "DELETE FROM completions WHERE habit_id = ?1 AND day = ?2",
                    params![habit_id, day],
                )?;
            } else {
                let total = active_count(&conn)?;
                conn.execute(
                    "INSERT INTO daily_targets(day, total) VALUES(?1, ?2)
                     ON CONFLICT(day) DO NOTHING",
                    params![day, total],
                )?;
                conn.execute(
                    "INSERT INTO completions(habit_id, day) VALUES(?1, ?2)",
                    params![habit_id, day],
                )?;
            }
        }
        self.day_state(day)
    }

    pub fn create_habit(&self, name: &str) -> Result<Vec<Habit>> {
        let clean = clean_name(name)?;
        let conn = self.lock()?;
        let count = active_count(&conn)?;
        if count >= MAX_HABITS {
            return Err(AppError::msg(format!(
                "Keep at most {MAX_HABITS} active habits"
            )));
        }
        let position: i64 = conn.query_row(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM habits",
            [],
            |row| row.get(0),
        )?;
        conn.execute(
            "INSERT INTO habits(name, position) VALUES(?1, ?2)",
            params![clean, position],
        )?;
        sync_today_target(&conn, &today_iso())?;
        active_habits(&conn)
    }

    pub fn rename_habit(&self, id: i64, name: &str) -> Result<Vec<Habit>> {
        let clean = clean_name(name)?;
        let conn = self.lock()?;
        let changed = conn.execute(
            "UPDATE habits SET name = ?1 WHERE id = ?2 AND archived = 0",
            params![clean, id],
        )?;
        if changed == 0 {
            return Err(AppError::msg("That habit no longer exists"));
        }
        active_habits(&conn)
    }

    pub fn reorder_habits(&self, ids: &[i64]) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        let active = active_habits(&conn)?;
        let active_ids: std::collections::HashSet<i64> = active.iter().map(|h| h.id).collect();
        let given: std::collections::HashSet<i64> = ids.iter().copied().collect();
        if ids.len() != active.len() || given != active_ids {
            return Err(AppError::msg("The habit order is out of date"));
        }
        let mut conn = conn;
        let tx = conn.transaction()?;
        for (position, id) in ids.iter().enumerate() {
            tx.execute(
                "UPDATE habits SET position = ?1 WHERE id = ?2",
                params![position as i64, id],
            )?;
        }
        tx.commit()?;
        active_habits(&conn)
    }

    pub fn archive_habit(&self, id: i64) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        let archived: Option<i64> = conn
            .query_row(
                "SELECT archived FROM habits WHERE id = ?1",
                params![id],
                |row| row.get(0),
            )
            .optional()?;
        match archived {
            None => return Err(AppError::msg("That habit no longer exists")),
            Some(1) => return Err(AppError::msg("That habit is already archived")),
            _ => {}
        }
        if active_count(&conn)? <= 1 {
            return Err(AppError::msg("Keep at least one active habit"));
        }
        conn.execute(
            "UPDATE habits SET archived = 1 WHERE id = ?1 AND archived = 0",
            params![id],
        )?;
        sync_today_target(&conn, &today_iso())?;
        active_habits(&conn)
    }

    pub fn restore_habit(&self, id: i64) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        let count = active_count(&conn)?;
        if count >= MAX_HABITS {
            return Err(AppError::msg(format!(
                "Keep at most {MAX_HABITS} active habits"
            )));
        }
        let position: i64 = conn.query_row(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM habits",
            [],
            |row| row.get(0),
        )?;
        let changed = conn.execute(
            "UPDATE habits SET archived = 0, position = ?1 WHERE id = ?2 AND archived = 1",
            params![position, id],
        )?;
        if changed == 0 {
            return Err(AppError::msg("That habit is already active"));
        }
        sync_today_target(&conn, &today_iso())?;
        active_habits(&conn)
    }

    pub fn delete_habit(&self, id: i64) -> Result<Vec<Habit>> {
        let conn = self.lock()?;
        let archived: Option<i64> = conn
            .query_row(
                "SELECT archived FROM habits WHERE id = ?1",
                params![id],
                |row| row.get(0),
            )
            .optional()?;
        match archived {
            None => return Err(AppError::msg("That habit no longer exists")),
            Some(0) if active_count(&conn)? <= 1 => {
                return Err(AppError::msg("Keep at least one active habit"))
            }
            _ => {}
        }
        conn.execute("DELETE FROM habits WHERE id = ?1", params![id])?;
        sync_today_target(&conn, &today_iso())?;
        active_habits(&conn)
    }

    pub fn range_summary(&self, start: &str, end: &str) -> Result<Vec<DaySummary>> {
        let start = parse_day(start)?;
        let end = parse_day(end)?;
        if end < start {
            return Ok(Vec::new());
        }
        if (end - start).num_days() > 366 * 200 {
            return Err(AppError::msg("That range is too large"));
        }
        let conn = self.lock()?;
        let (counts, targets) = summary_maps(&conn, start, end)?;
        let mut days: BTreeMap<NaiveDate, (i64, Option<i64>)> = BTreeMap::new();
        for (day, count) in counts {
            days.entry(day).or_insert((0, None)).0 = count;
        }
        for (day, total) in targets {
            days.entry(day).or_insert((0, None)).1 = Some(total);
        }
        Ok(days
            .into_iter()
            .map(|(day, (count, target))| DaySummary {
                day: iso(day),
                count,
                target,
            })
            .collect())
    }

    pub fn completions_range(&self, start: &str, end: &str) -> Result<Vec<HabitMark>> {
        let start = parse_day(start)?;
        let end = parse_day(end)?;
        if end < start {
            return Ok(Vec::new());
        }
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT habit_id, day FROM completions WHERE day BETWEEN ?1 AND ?2 ORDER BY day",
        )?;
        let rows = stmt.query_map(params![iso(start), iso(end)], |row| {
            Ok(HabitMark {
                habit_id: row.get(0)?,
                day: row.get(1)?,
            })
        })?;
        Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
    }

    pub fn stats(&self, start: &str, end: &str) -> Result<Stats> {
        let start = parse_day(start)?;
        let end = parse_day(end)?;
        let conn = self.lock()?;
        if end < start {
            return Ok(Stats {
                days: 0,
                perfect_days: 0,
                active_days: 0,
                rate: 0.0,
                best_streak: 0,
                per_habit: Vec::new(),
            });
        }
        let days = (end - start).num_days() + 1;
        let active = active_count(&conn)?;
        let (counts, targets) = summary_maps(&conn, start, end)?;
        let mut perfect = 0;
        let mut active_days = 0;
        let mut best = 0;
        let mut run = 0;
        let mut cursor = start;
        while cursor <= end {
            let count = counts.get(&cursor).copied().unwrap_or(0);
            let target = targets.get(&cursor).copied().unwrap_or(active);
            if count > 0 {
                active_days += 1;
            }
            if target > 0 && count >= target {
                perfect += 1;
                run += 1;
                best = best.max(run);
            } else {
                run = 0;
            }
            cursor += Duration::days(1);
        }

        let mut per_habit: Vec<HabitStat> = active_habits(&conn)?
            .into_iter()
            .map(|habit| HabitStat {
                habit_id: habit.id,
                name: habit.name,
                completions: 0,
                rate: 0.0,
            })
            .collect();
        let mut stmt = conn.prepare(
            "SELECT c.habit_id, h.name, COUNT(*)
             FROM completions c JOIN habits h ON h.id = c.habit_id
             WHERE c.day BETWEEN ?1 AND ?2
             GROUP BY c.habit_id",
        )?;
        let rows = stmt.query_map(params![iso(start), iso(end)], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
            ))
        })?;
        for row in rows {
            let (id, name, count) = row?;
            if let Some(stat) = per_habit.iter_mut().find(|s| s.habit_id == id) {
                stat.completions = count;
            } else {
                per_habit.push(HabitStat {
                    habit_id: id,
                    name,
                    completions: count,
                    rate: 0.0,
                });
            }
        }
        for stat in &mut per_habit {
            stat.rate = if days > 0 {
                stat.completions as f64 / days as f64
            } else {
                0.0
            };
        }

        Ok(Stats {
            days,
            perfect_days: perfect,
            active_days,
            rate: if days > 0 {
                perfect as f64 / days as f64
            } else {
                0.0
            },
            best_streak: best,
            per_habit,
        })
    }

    pub fn get_note(&self, day: &str) -> Result<Option<String>> {
        parse_day(day)?;
        let conn = self.lock()?;
        note_for(&conn, day)
    }

    pub fn set_note(&self, day: &str, body: &str) -> Result<Option<String>> {
        parse_day(day)?;
        let conn = self.lock()?;
        let clean = body.trim();
        if clean.is_empty() {
            conn.execute("DELETE FROM day_notes WHERE day = ?1", params![day])?;
            return Ok(None);
        }
        if clean.chars().count() > 5000 {
            return Err(AppError::msg("Notes are limited to 5000 characters"));
        }
        conn.execute(
            "INSERT INTO day_notes(day, body) VALUES(?1, ?2)
             ON CONFLICT(day) DO UPDATE SET body = excluded.body",
            params![day, clean],
        )?;
        Ok(Some(clean.to_string()))
    }

    pub fn update_settings(&self, patch: SettingsPatch) -> Result<Settings> {
        let today = today();
        let current = self.settings()?;
        let mut values: Vec<(String, Value)> = Vec::new();

        if let Some(theme) = patch.theme {
            if !THEMES.contains(&theme.as_str()) {
                return Err(AppError::msg("Unknown theme"));
            }
            values.push(("theme".into(), json!(theme)));
        }
        if let Some(value) = patch.start_date {
            parse_day(&value)?;
            values.push(("start_date".into(), json!(value)));
        }
        if let Some(value) = patch.birth_date {
            let birth = parse_day(&value)?;
            if birth >= today {
                return Err(AppError::msg("Birth date must be in the past"));
            }
            values.push(("birth_date".into(), json!(value)));
        }
        if let Some(value) = patch.lifespan {
            if !(1..=150).contains(&value) {
                return Err(AppError::msg("Expected age must be between 1 and 150"));
            }
            values.push(("lifespan".into(), json!(value)));
        }
        if let Some(value) = patch.week_start {
            if value != 0 && value != 1 {
                return Err(AppError::msg("Week start must be Sunday or Monday"));
            }
            values.push(("week_start".into(), json!(value)));
        }
        if let Some(value) = patch.reduce_motion {
            values.push(("reduce_motion".into(), json!(value)));
        }
        if let Some(value) = patch.reminder_enabled {
            values.push(("reminder_enabled".into(), json!(value)));
        }
        if let Some(value) = patch.reminder_time {
            if !parse_time(&value) {
                return Err(AppError::msg("Reminder time must be HH:MM"));
            }
            values.push(("reminder_time".into(), json!(value)));
        }
        if let Some(value) = patch.minimize_to_tray {
            values.push(("minimize_to_tray".into(), json!(value)));
        }
        if let Some(value) = patch.launch_at_login {
            values.push(("launch_at_login".into(), json!(value)));
        }
        if let Some(value) = patch.onboarded {
            values.push(("onboarded".into(), json!(value)));
        }

        let birth = values
            .iter()
            .find(|(key, _)| key == "birth_date")
            .and_then(|(_, value)| value.as_str())
            .map(parse_day)
            .transpose()?
            .unwrap_or_else(|| parse_day(&current.birth_date).unwrap_or(today));
        let lifespan = values
            .iter()
            .find(|(key, _)| key == "lifespan")
            .and_then(|(_, value)| value.as_i64())
            .unwrap_or(current.lifespan);
        let end = NaiveDate::from_ymd_opt(birth.year() + lifespan as i32, birth.month(), birth.day())
            .or_else(|| NaiveDate::from_ymd_opt(birth.year() + lifespan as i32, birth.month(), 28))
            .ok_or_else(|| AppError::msg("That lifespan is out of range"))?;
        if end <= today {
            return Err(AppError::msg(
                "Expected age must be later than your current age",
            ));
        }

        if !values.is_empty() {
            let conn = self.lock()?;
            let tx = conn.unchecked_transaction()?;
            for (key, value) in values {
                tx.execute(
                    "INSERT INTO settings(key, value) VALUES(?1, ?2)
                     ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    params![key, value.to_string()],
                )?;
            }
            tx.commit()?;
        }
        self.settings()
    }

    pub fn minimize_to_tray(&self) -> Result<bool> {
        Ok(self.settings()?.minimize_to_tray)
    }

    fn bundle(&self) -> Result<ExportBundle> {
        let conn = self.lock()?;
        let mut settings = Map::new();
        let mut stmt = conn.prepare("SELECT key, value FROM settings")?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;
        for row in rows {
            let (key, raw) = row?;
            let value = serde_json::from_str(&raw).unwrap_or(Value::String(raw));
            settings.insert(key, value);
        }

        let habits = all_habits(&conn)?;
        let mut stmt =
            conn.prepare("SELECT habit_id, day FROM completions ORDER BY day, habit_id")?;
        let completions = stmt
            .query_map([], |row| {
                Ok(Completion {
                    habit_id: row.get(0)?,
                    day: row.get(1)?,
                })
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        let mut stmt = conn.prepare("SELECT day, total FROM daily_targets ORDER BY day")?;
        let targets = stmt
            .query_map([], |row| {
                Ok(DayTarget {
                    day: row.get(0)?,
                    total: row.get(1)?,
                })
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        let mut stmt = conn.prepare("SELECT day, body FROM day_notes ORDER BY day")?;
        let notes = stmt
            .query_map([], |row| {
                Ok(Note {
                    day: row.get(0)?,
                    body: row.get(1)?,
                })
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;

        Ok(ExportBundle {
            version: 1,
            exported_at: Local::now().to_rfc3339(),
            app: "span".into(),
            settings,
            habits,
            completions,
            targets,
            notes,
        })
    }

    pub fn export_json(&self) -> Result<String> {
        Ok(serde_json::to_string_pretty(&self.bundle()?)?)
    }

    pub fn export_to(&self, path: &str) -> Result<String> {
        let json = self.export_json()?;
        let path = PathBuf::from(path);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, json)?;
        Ok(path.to_string_lossy().to_string())
    }

    pub fn import_from(&self, path: &str) -> Result<ImportResult> {
        let text = fs::read_to_string(path)?;
        self.import_json(&text)
    }

    pub fn import_json(&self, text: &str) -> Result<ImportResult> {
        let bundle: ExportBundle = serde_json::from_str(text)
            .map_err(|_| AppError::msg("That file is not a span backup"))?;
        if bundle.version != 1 {
            return Err(AppError::msg("This backup was made by a newer version"));
        }
        let mut conn = self.lock()?;
        let tx = conn.transaction()?;
        tx.execute("DELETE FROM completions", [])?;
        tx.execute("DELETE FROM daily_targets", [])?;
        tx.execute("DELETE FROM day_notes", [])?;
        tx.execute("DELETE FROM habits", [])?;
        tx.execute("DELETE FROM settings", [])?;

        let mut imported_ids = std::collections::HashSet::new();
        for habit in &bundle.habits {
            if habit.name.trim().is_empty() {
                continue;
            }
            tx.execute(
                "INSERT INTO habits(id, name, position, archived) VALUES(?1, ?2, ?3, ?4)",
                params![
                    habit.id,
                    habit.name.trim(),
                    habit.position,
                    if habit.archived { 1 } else { 0 }
                ],
            )?;
            imported_ids.insert(habit.id);
        }
        // A check-in for a habit that was skipped or missing would violate the
        // foreign key and abort the whole import, so drop those rows instead.
        let completions: Vec<&Completion> = bundle
            .completions
            .iter()
            .filter(|completion| imported_ids.contains(&completion.habit_id))
            .collect();
        for completion in &completions {
            tx.execute(
                "INSERT OR IGNORE INTO completions(habit_id, day) VALUES(?1, ?2)",
                params![completion.habit_id, completion.day],
            )?;
        }
        for target in &bundle.targets {
            tx.execute(
                "INSERT OR REPLACE INTO daily_targets(day, total) VALUES(?1, ?2)",
                params![target.day, target.total],
            )?;
        }
        for note in &bundle.notes {
            if !note.body.trim().is_empty() {
                tx.execute(
                    "INSERT OR REPLACE INTO day_notes(day, body) VALUES(?1, ?2)",
                    params![note.day, note.body],
                )?;
            }
        }
        for (key, value) in &bundle.settings {
            tx.execute(
                "INSERT INTO settings(key, value) VALUES(?1, ?2)
                 ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                params![key, value.to_string()],
            )?;
        }
        tx.execute(
            "INSERT INTO settings(key, value) VALUES('onboarded', 'true')
             ON CONFLICT(key) DO UPDATE SET value = 'true'",
            [],
        )?;
        tx.commit()?;
        seed_defaults(&conn)?;

        Ok(ImportResult {
            habits: imported_ids.len(),
            completions: completions.len(),
            days: bundle.targets.len(),
            notes: bundle.notes.len(),
        })
    }

    pub fn import_legacy(&self, path: &Path) -> Result<bool> {
        if !path.exists() {
            return Ok(false);
        }
        let legacy = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
        let habits: Vec<(i64, String, i64, i64)> = {
            let mut stmt = match legacy.prepare("SELECT id, name, position, archived FROM habits") {
                Ok(stmt) => stmt,
                Err(_) => return Ok(false),
            };
            stmt.query_map([], |row| {
                Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?
        };
        if habits.is_empty() {
            return Ok(false);
        }
        let completions: Vec<(i64, String)> = {
            let mut stmt = legacy
                .prepare("SELECT habit_id, day FROM completions")
                .unwrap_or_else(|_| legacy.prepare("SELECT 1, '1970-01-01' WHERE 0").unwrap());
            stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        let targets: Vec<(String, i64)> = {
            let mut stmt = legacy
                .prepare("SELECT day, total FROM daily_targets")
                .unwrap_or_else(|_| legacy.prepare("SELECT '1970-01-01', 0 WHERE 0").unwrap());
            stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        let legacy_settings: Vec<(String, String)> = {
            let mut stmt = legacy
                .prepare("SELECT key, value FROM settings")
                .unwrap_or_else(|_| legacy.prepare("SELECT 'x', 'null' WHERE 0").unwrap());
            stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };

        let mut conn = self.lock()?;
        let tx = conn.transaction()?;
        tx.execute("DELETE FROM completions", [])?;
        tx.execute("DELETE FROM daily_targets", [])?;
        tx.execute("DELETE FROM day_notes", [])?;
        tx.execute("DELETE FROM habits", [])?;
        for (id, name, position, archived) in habits {
            tx.execute(
                "INSERT INTO habits(id, name, position, archived) VALUES(?1, ?2, ?3, ?4)",
                params![id, name, position, archived],
            )?;
        }
        for (habit_id, day) in completions {
            tx.execute(
                "INSERT OR IGNORE INTO completions(habit_id, day) VALUES(?1, ?2)",
                params![habit_id, day],
            )?;
        }
        for (day, total) in targets {
            tx.execute(
                "INSERT OR REPLACE INTO daily_targets(day, total) VALUES(?1, ?2)",
                params![day, total],
            )?;
        }
        for (key, raw) in legacy_settings {
            if matches!(
                key.as_str(),
                "theme" | "start_date" | "birth_date" | "lifespan"
            ) {
                let value = serde_json::from_str::<Value>(&raw)
                    .map(|value| value.to_string())
                    .unwrap_or_else(|_| json!(raw).to_string());
                tx.execute(
                    "INSERT INTO settings(key, value) VALUES(?1, ?2)
                     ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    params![key, value],
                )?;
            }
        }
        let now = Local::now().to_rfc3339();
        tx.execute(
            "INSERT INTO settings(key, value) VALUES('legacy_imported_at', ?1)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            params![json!(now).to_string()],
        )?;
        tx.execute(
            "INSERT INTO settings(key, value) VALUES('onboarded', 'true')
             ON CONFLICT(key) DO UPDATE SET value = 'true'",
            [],
        )?;
        tx.commit()?;
        seed_defaults(&conn)?;
        Ok(true)
    }

    pub fn auto_backup(&self) -> Result<Option<String>> {
        let dir = self.dir.join("backups");
        fs::create_dir_all(&dir)?;
        let path = dir.join(format!("span-{}.json", today_iso()));
        if path.exists() {
            return Ok(None);
        }
        let json = self.export_json()?;
        let tmp = path.with_extension("json.tmp");
        fs::write(&tmp, json)?;
        fs::rename(&tmp, &path)?;
        prune_backups(&dir)?;
        Ok(Some(path.to_string_lossy().to_string()))
    }

    pub fn backup_now(&self) -> Result<String> {
        let dir = self.dir.join("backups");
        fs::create_dir_all(&dir)?;
        let stamp = Local::now().format("%Y-%m-%d-%H%M%S");
        let path = dir.join(format!("span-{stamp}.json"));
        let json = self.export_json()?;
        fs::write(&path, json)?;
        prune_backups(&dir)?;
        Ok(path.to_string_lossy().to_string())
    }
}

fn prune_backups(dir: &Path) -> Result<()> {
    let mut entries: Vec<PathBuf> = fs::read_dir(dir)?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| {
            path.extension().and_then(|value| value.to_str()) == Some("json")
                && path
                    .file_name()
                    .and_then(|value| value.to_str())
                    .is_some_and(|name| name.starts_with("span-"))
        })
        .collect();
    entries.sort();
    while entries.len() > 14 {
        let oldest = entries.remove(0);
        let _ = fs::remove_file(oldest);
    }
    Ok(())
}

fn migrate(conn: &Connection) -> Result<()> {
    let version: i64 = conn.query_row("PRAGMA user_version", [], |row| row.get(0))?;
    if version < 1 {
        conn.execute_batch(SCHEMA)?;
        conn.pragma_update(None, "user_version", 1)?;
    }
    Ok(())
}

fn seed_defaults(conn: &Connection) -> Result<()> {
    let today = today();
    let defaults: [(&str, Value); 11] = [
        ("theme", json!("forest")),
        ("start_date", json!(iso(today))),
        ("birth_date", json!(default_birth(today))),
        ("lifespan", json!(85)),
        ("week_start", json!(1)),
        ("reduce_motion", json!(false)),
        ("reminder_enabled", json!(false)),
        ("reminder_time", json!("20:00")),
        ("minimize_to_tray", json!(true)),
        ("launch_at_login", json!(false)),
        ("onboarded", json!(false)),
    ];
    for (key, value) in defaults {
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?1, ?2) ON CONFLICT(key) DO NOTHING",
            params![key, value.to_string()],
        )?;
    }
    Ok(())
}

fn setting_value(conn: &Connection, key: &str) -> Result<Option<Value>> {
    let raw: Option<String> = conn
        .query_row(
            "SELECT value FROM settings WHERE key = ?1",
            params![key],
            |row| row.get(0),
        )
        .optional()?;
    Ok(raw.and_then(|raw| serde_json::from_str(&raw).ok()))
}

fn settings_from(conn: &Connection) -> Result<Settings> {
    let get = |key: &str| setting_value(conn, key).ok().flatten();
    let text = |key: &str| {
        get(key)
            .and_then(|value| value.as_str().map(str::to_string))
            .filter(|value| !value.is_empty())
    };
    let flag = |key: &str, fallback: bool| {
        get(key)
            .and_then(|value| value.as_bool())
            .unwrap_or(fallback)
    };
    let number = |key: &str, fallback: i64| {
        get(key)
            .and_then(|value| value.as_i64())
            .unwrap_or(fallback)
    };

    let today = today();
    let start_date = text("start_date")
        .filter(|value| parse_day(value).is_ok())
        .unwrap_or_else(today_iso);
    let birth_date = text("birth_date")
        .filter(|value| parse_day(value).is_ok())
        .unwrap_or_else(|| default_birth(today));
    let lifespan = number("lifespan", 85).clamp(1, 150);
    let week_start = if number("week_start", 1) == 0 { 0 } else { 1 };
    let reminder_time = text("reminder_time")
        .filter(|value| parse_time(value))
        .unwrap_or_else(|| "20:00".into());
    let theme = text("theme")
        .filter(|value| THEMES.contains(&value.as_str()))
        .unwrap_or_else(|| "forest".into());

    Ok(Settings {
        theme,
        start_date,
        birth_date,
        lifespan,
        week_start,
        reduce_motion: flag("reduce_motion", false),
        reminder_enabled: flag("reminder_enabled", false),
        reminder_time,
        minimize_to_tray: flag("minimize_to_tray", true),
        launch_at_login: flag("launch_at_login", false),
        onboarded: flag("onboarded", false),
    })
}

fn habit_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Habit> {
    Ok(Habit {
        id: row.get(0)?,
        name: row.get(1)?,
        position: row.get(2)?,
        archived: row.get::<_, i64>(3)? != 0,
    })
}

fn active_habits(conn: &Connection) -> Result<Vec<Habit>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, position, archived FROM habits WHERE archived = 0 ORDER BY position, id",
    )?;
    let rows = stmt.query_map([], habit_from_row)?;
    Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
}

fn all_habits(conn: &Connection) -> Result<Vec<Habit>> {
    let mut stmt =
        conn.prepare("SELECT id, name, position, archived FROM habits ORDER BY archived, position, id")?;
    let rows = stmt.query_map([], habit_from_row)?;
    Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
}

fn active_count(conn: &Connection) -> Result<i64> {
    Ok(conn.query_row(
        "SELECT COUNT(*) FROM habits WHERE archived = 0",
        [],
        |row| row.get(0),
    )?)
}

fn clean_name(name: &str) -> Result<String> {
    let clean = name.trim();
    if clean.is_empty() {
        return Err(AppError::msg("Give the habit a name"));
    }
    if clean.chars().count() > 80 {
        return Err(AppError::msg("Habit names are limited to 80 characters"));
    }
    Ok(clean.to_string())
}

fn sync_today_target(conn: &Connection, day: &str) -> Result<()> {
    let total = active_count(conn)?;
    conn.execute(
        "INSERT INTO daily_targets(day, total) VALUES(?1, ?2)
         ON CONFLICT(day) DO UPDATE SET total = excluded.total",
        params![day, total],
    )?;
    Ok(())
}

fn target_for(conn: &Connection, day: &str) -> Result<Option<i64>> {
    Ok(conn
        .query_row(
            "SELECT total FROM daily_targets WHERE day = ?1",
            params![day],
            |row| row.get(0),
        )
        .optional()?)
}

fn completed_ids(conn: &Connection, day: &str) -> Result<Vec<i64>> {
    let mut stmt =
        conn.prepare("SELECT habit_id FROM completions WHERE day = ?1 ORDER BY habit_id")?;
    let rows = stmt.query_map(params![day], |row| row.get(0))?;
    Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
}

fn note_for(conn: &Connection, day: &str) -> Result<Option<String>> {
    Ok(conn
        .query_row(
            "SELECT body FROM day_notes WHERE day = ?1",
            params![day],
            |row| row.get(0),
        )
        .optional()?)
}

fn summary_maps(
    conn: &Connection,
    start: NaiveDate,
    end: NaiveDate,
) -> Result<(BTreeMap<NaiveDate, i64>, BTreeMap<NaiveDate, i64>)> {
    let mut counts: BTreeMap<NaiveDate, i64> = BTreeMap::new();
    let mut stmt = conn.prepare(
        "SELECT day, COUNT(*) FROM completions WHERE day BETWEEN ?1 AND ?2 GROUP BY day",
    )?;
    let rows = stmt.query_map(params![iso(start), iso(end)], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
    })?;
    for row in rows {
        let (day, count) = row?;
        if let Ok(day) = parse_day(&day) {
            counts.insert(day, count);
        }
    }

    let mut targets: BTreeMap<NaiveDate, i64> = BTreeMap::new();
    let mut stmt =
        conn.prepare("SELECT day, total FROM daily_targets WHERE day BETWEEN ?1 AND ?2")?;
    let rows = stmt.query_map(params![iso(start), iso(end)], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
    })?;
    for row in rows {
        let (day, total) = row?;
        if let Ok(day) = parse_day(&day) {
            targets.insert(day, total);
        }
    }
    Ok((counts, targets))
}

fn current_streak(conn: &Connection, through: NaiveDate, active: i64) -> Result<i64> {
    if active == 0 {
        return Ok(0);
    }
    let settings = settings_from(conn)?;
    let start = parse_day(&settings.start_date).unwrap_or(through);
    if start > through {
        return Ok(0);
    }
    let (counts, targets) = summary_maps(conn, start, through)?;
    let target = |day: NaiveDate| targets.get(&day).copied().unwrap_or(active);
    let mut cursor = through;
    if counts.get(&cursor).copied().unwrap_or(0) < target(cursor) {
        cursor -= Duration::days(1);
    }
    let mut streak = 0;
    while cursor >= start && counts.get(&cursor).copied().unwrap_or(0) >= target(cursor) {
        streak += 1;
        cursor -= Duration::days(1);
    }
    Ok(streak)
}

fn streaks(conn: &Connection, through: NaiveDate, active: i64) -> Result<Streak> {
    if active == 0 {
        return Ok(Streak::default());
    }
    let settings = settings_from(conn)?;
    let start = parse_day(&settings.start_date).unwrap_or(through);
    if start > through {
        return Ok(Streak::default());
    }
    let (counts, targets) = summary_maps(conn, start, through)?;
    let target = |day: NaiveDate| targets.get(&day).copied().unwrap_or(active);

    let mut cursor = through;
    if counts.get(&cursor).copied().unwrap_or(0) < target(cursor) {
        cursor -= Duration::days(1);
    }
    let mut current = 0;
    while cursor >= start && counts.get(&cursor).copied().unwrap_or(0) >= target(cursor) {
        current += 1;
        cursor -= Duration::days(1);
    }

    let mut best = 0;
    let mut run = 0;
    let mut day = start;
    while day <= through {
        if counts.get(&day).copied().unwrap_or(0) >= target(day) {
            run += 1;
            best = best.max(run);
        } else {
            run = 0;
        }
        day += Duration::days(1);
    }

    Ok(Streak { current, best })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn scratch(name: &str) -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_nanos())
            .unwrap_or(0);
        let dir = std::env::temp_dir().join(format!(
            "span-test-{name}-{}-{stamp}",
            std::process::id()
        ));
        fs::create_dir_all(&dir).expect("scratch directory");
        dir
    }

    #[test]
    fn opens_with_defaults() {
        let dir = scratch("defaults");
        let db = Db::open_at(dir.clone()).expect("open");
        let settings = db.settings().expect("settings");
        assert_eq!(settings.theme, "forest");
        assert_eq!(settings.week_start, 1);
        assert_eq!(settings.reminder_time, "20:00");
        assert!(!settings.onboarded);
        assert!(!settings.reminder_enabled);
        assert!(db.active_habits().expect("habits").is_empty());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn rejects_bad_days() {
        let dir = scratch("days");
        let db = Db::open_at(dir.clone()).expect("open");
        assert!(parse_day("2026-13-01").is_err());
        assert!(parse_day("2026-1-01").is_err());
        assert!(parse_day("not-a-date").is_err());
        assert!(db.day_state("2026-02-30").is_err());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn toggling_tracks_targets_and_streaks() {
        let dir = scratch("toggle");
        let db = Db::open_at(dir.clone()).expect("open");
        db.create_habit("Read").expect("habit");
        db.create_habit("Move").expect("habit");
        let today = today_iso();
        let state = db.day_state(&today).expect("day");

        assert_eq!(state.target, 2);
        assert_eq!(state.habits.len(), 2);
        assert!(state.completed.is_empty());

        let first = state.habits[0].id;
        let after_first = db.toggle(first, &today).expect("toggle");
        assert_eq!(after_first.completed, vec![first]);
        assert_eq!(after_first.streak, 0);

        let second = after_first.habits[1].id;
        let after_second = db.toggle(second, &today).expect("toggle");
        assert_eq!(after_second.completed.len(), 2);
        assert_eq!(after_second.streak, 1);

        let streak = db.streak(None).expect("streak");
        assert_eq!(streak.current, 1);
        assert_eq!(streak.best, 1);

        let undone = db.toggle(first, &today).expect("toggle");
        assert_eq!(undone.completed, vec![second]);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn refuses_future_check_ins() {
        let dir = scratch("future");
        let db = Db::open_at(dir.clone()).expect("open");
        let habit = db.create_habit("Read").expect("habit").remove(0);
        let tomorrow = iso(today() + Duration::days(1));
        assert!(db.toggle(habit.id, &tomorrow).is_err());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn keeps_at_least_one_active_habit() {
        let dir = scratch("guard");
        let db = Db::open_at(dir.clone()).expect("open");
        let habit = db.create_habit("Only").expect("habit").remove(0);
        assert!(db.archive_habit(habit.id).is_err());
        assert!(db.delete_habit(habit.id).is_err());
        assert_eq!(db.active_habits().expect("habits").len(), 1);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn caps_active_habits() {
        let dir = scratch("cap");
        let db = Db::open_at(dir.clone()).expect("open");
        for index in 0..MAX_HABITS {
            db.create_habit(&format!("Habit {index}")).expect("habit");
        }
        assert!(db.create_habit("One too many").is_err());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn notes_roundtrip_and_clear() {
        let dir = scratch("notes");
        let db = Db::open_at(dir.clone()).expect("open");
        let today = today_iso();
        assert_eq!(db.get_note(&today).expect("note"), None);
        assert_eq!(
            db.set_note(&today, "  a good day  ").expect("note"),
            Some("a good day".to_string())
        );
        assert_eq!(
            db.get_note(&today).expect("note").as_deref(),
            Some("a good day")
        );
        assert_eq!(db.set_note(&today, "   ").expect("note"), None);
        assert_eq!(db.get_note(&today).expect("note"), None);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn export_and_import_roundtrip() {
        let dir = scratch("export");
        let db = Db::open_at(dir.clone()).expect("open");
        let habit = db.create_habit("Write").expect("habit").remove(0);
        let today = today_iso();
        db.toggle(habit.id, &today).expect("toggle");
        db.set_note(&today, "a line").expect("note");
        let json = db.export_json().expect("export");

        db.create_habit("Extra").expect("habit");
        assert_eq!(db.active_habits().expect("habits").len(), 2);

        let result = db.import_json(&json).expect("import");
        assert_eq!(result.habits, 1);
        assert_eq!(result.completions, 1);
        assert_eq!(db.active_habits().expect("habits").len(), 1);

        let state = db.day_state(&today).expect("day");
        assert_eq!(state.completed.len(), 1);
        assert_eq!(state.note.as_deref(), Some("a line"));
        assert!(db.settings().expect("settings").onboarded);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn import_skips_check_ins_for_missing_habits() {
        let dir = scratch("orphans");
        let db = Db::open_at(dir.clone()).expect("open");
        let habit = db.create_habit("Write").expect("habit").remove(0);
        let today = today_iso();
        db.toggle(habit.id, &today).expect("toggle");
        let mut bundle: Value =
            serde_json::from_str(&db.export_json().expect("export")).expect("json");
        bundle["completions"]
            .as_array_mut()
            .expect("completions")
            .push(json!({ "habitId": 9999, "day": today }));

        let result = db.import_json(&bundle.to_string()).expect("import");
        assert_eq!(result.habits, 1);
        assert_eq!(result.completions, 1);
        assert_eq!(db.day_state(&today).expect("day").completed, vec![habit.id]);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn imports_legacy_database() {
        let dir = scratch("legacy");
        let legacy_path = dir.join("span.db");
        let legacy = Connection::open(&legacy_path).expect("legacy");
        legacy
            .execute_batch(
                r#"
                CREATE TABLE habits (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE completions (
                    habit_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    PRIMARY KEY (habit_id, day)
                );
                CREATE TABLE daily_targets (day TEXT PRIMARY KEY, total INTEGER NOT NULL);
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO habits(id, name, position, archived) VALUES
                    (1, 'Stretch', 0, 0),
                    (2, 'Old habit', 1, 1);
                INSERT INTO completions(habit_id, day) VALUES
                    (1, '2026-10-31'),
                    (1, '2026-11-01');
                INSERT INTO daily_targets(day, total) VALUES
                    ('2026-10-31', 1),
                    ('2026-11-01', 1);
                INSERT INTO settings(key, value) VALUES
                    ('theme', '"ocean"'),
                    ('start_date', '"2026-10-01"'),
                    ('lifespan', '90');
                "#,
            )
            .expect("legacy schema");
        drop(legacy);

        let db = Db::open_at(dir.clone()).expect("open");
        assert!(db.legacy_available().expect("legacy flag"));
        assert!(db.import_legacy(&legacy_path).expect("import"));
        assert!(!db.legacy_available().expect("legacy flag"));

        let settings = db.settings().expect("settings");
        assert_eq!(settings.theme, "ocean");
        assert_eq!(settings.start_date, "2026-10-01");
        assert_eq!(settings.lifespan, 90);
        assert!(settings.onboarded);

        assert_eq!(db.active_habits().expect("habits").len(), 1);
        let summary = db.range_summary("2026-10-31", "2026-11-01").expect("range");
        assert_eq!(summary.len(), 2);
        assert_eq!(summary[0].count, 1);
        assert_eq!(summary[0].target, Some(1));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn renames_and_reorders() {
        let dir = scratch("order");
        let db = Db::open_at(dir.clone()).expect("open");
        let habits = db.create_habit("One").expect("habit");
        let first = habits[0].id;
        let habits = db.create_habit("Two").expect("habit");
        let second = habits[1].id;

        let renamed = db.rename_habit(first, "  Uno  ").expect("rename");
        assert_eq!(renamed[0].name, "Uno");

        let reordered = db.reorder_habits(&[second, first]).expect("reorder");
        assert_eq!(reordered[0].id, second);
        assert_eq!(reordered[1].id, first);

        assert!(db.reorder_habits(&[first]).is_err());
        let _ = fs::remove_dir_all(dir);
    }
}
