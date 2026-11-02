use std::path::PathBuf;

use tauri::State;

use crate::{
    db::{today_iso, Db},
    error::Result,
    models::*,
};

pub struct AppState {
    pub db: Db,
    pub dir: PathBuf,
}

#[tauri::command]
pub fn bootstrap(state: State<'_, AppState>) -> Result<Bootstrap> {
    let settings = state.db.settings()?;
    let habits = state.db.active_habits()?;
    let streak = state.db.streak(None)?.current;
    let legacy_available = state.db.legacy_available()?;
    Ok(Bootstrap {
        settings,
        habits,
        today: today_iso(),
        streak,
        legacy_available,
        data_dir: state.dir.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn get_day(state: State<'_, AppState>, day: String) -> Result<DayState> {
    state.db.day_state(&day)
}

#[tauri::command]
pub fn toggle_completion(
    state: State<'_, AppState>,
    habit_id: i64,
    day: String,
) -> Result<DayState> {
    state.db.toggle(habit_id, &day)
}

#[tauri::command]
pub fn range_summary(
    state: State<'_, AppState>,
    start: String,
    end: String,
) -> Result<Vec<DaySummary>> {
    state.db.range_summary(&start, &end)
}

#[tauri::command]
pub fn completions_range(
    state: State<'_, AppState>,
    start: String,
    end: String,
) -> Result<Vec<HabitMark>> {
    state.db.completions_range(&start, &end)
}

#[tauri::command]
pub fn list_habits(state: State<'_, AppState>) -> Result<Vec<Habit>> {
    state.db.active_habits()
}

#[tauri::command]
pub fn list_archived_habits(state: State<'_, AppState>) -> Result<Vec<Habit>> {
    state.db.archived_habits()
}

#[tauri::command]
pub fn create_habit(state: State<'_, AppState>, name: String) -> Result<Vec<Habit>> {
    state.db.create_habit(&name)
}

#[tauri::command]
pub fn rename_habit(state: State<'_, AppState>, id: i64, name: String) -> Result<Vec<Habit>> {
    state.db.rename_habit(id, &name)
}

#[tauri::command]
pub fn reorder_habits(state: State<'_, AppState>, ids: Vec<i64>) -> Result<Vec<Habit>> {
    state.db.reorder_habits(&ids)
}

#[tauri::command]
pub fn archive_habit(state: State<'_, AppState>, id: i64) -> Result<Vec<Habit>> {
    state.db.archive_habit(id)
}

#[tauri::command]
pub fn restore_habit(state: State<'_, AppState>, id: i64) -> Result<Vec<Habit>> {
    state.db.restore_habit(id)
}

#[tauri::command]
pub fn delete_habit(state: State<'_, AppState>, id: i64) -> Result<Vec<Habit>> {
    state.db.delete_habit(id)
}

#[tauri::command]
pub fn get_settings(state: State<'_, AppState>) -> Result<Settings> {
    state.db.settings()
}

#[tauri::command]
pub fn update_settings(
    state: State<'_, AppState>,
    patch: SettingsPatch,
) -> Result<Settings> {
    state.db.update_settings(patch)
}

#[tauri::command]
pub fn streak(state: State<'_, AppState>, through: Option<String>) -> Result<Streak> {
    state.db.streak(through.as_deref())
}

#[tauri::command]
pub fn stats(state: State<'_, AppState>, start: String, end: String) -> Result<Stats> {
    state.db.stats(&start, &end)
}

#[tauri::command]
pub fn get_note(state: State<'_, AppState>, day: String) -> Result<Option<String>> {
    state.db.get_note(&day)
}

#[tauri::command]
pub fn set_note(
    state: State<'_, AppState>,
    day: String,
    body: String,
) -> Result<Option<String>> {
    state.db.set_note(&day, &body)
}

#[tauri::command]
pub fn export_to(state: State<'_, AppState>, path: String) -> Result<String> {
    state.db.export_to(&path)
}

#[tauri::command]
pub fn import_from(state: State<'_, AppState>, path: String) -> Result<ImportResult> {
    let result = state.db.import_from(&path)?;
    let _ = state.db.auto_backup();
    Ok(result)
}

#[tauri::command]
pub fn backup_now(state: State<'_, AppState>) -> Result<String> {
    state.db.backup_now()
}

#[tauri::command]
pub fn import_legacy(state: State<'_, AppState>) -> Result<bool> {
    let path = state.db.legacy_path();
    let imported = state.db.import_legacy(&path)?;
    if imported {
        let _ = state.db.auto_backup();
    }
    Ok(imported)
}
