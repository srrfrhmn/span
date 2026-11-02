use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Habit {
    pub id: i64,
    pub name: String,
    pub position: i64,
    pub archived: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DayState {
    pub day: String,
    pub habits: Vec<Habit>,
    pub completed: Vec<i64>,
    pub target: i64,
    pub note: Option<String>,
    pub streak: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DaySummary {
    pub day: String,
    pub count: i64,
    pub target: Option<i64>,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Streak {
    pub current: i64,
    pub best: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Settings {
    pub theme: String,
    pub start_date: String,
    pub birth_date: String,
    pub lifespan: i64,
    pub week_start: i64,
    pub reduce_motion: bool,
    pub reminder_enabled: bool,
    pub reminder_time: String,
    pub minimize_to_tray: bool,
    pub launch_at_login: bool,
    pub onboarded: bool,
}

#[derive(Debug, Default, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsPatch {
    pub theme: Option<String>,
    pub start_date: Option<String>,
    pub birth_date: Option<String>,
    pub lifespan: Option<i64>,
    pub week_start: Option<i64>,
    pub reduce_motion: Option<bool>,
    pub reminder_enabled: Option<bool>,
    pub reminder_time: Option<String>,
    pub minimize_to_tray: Option<bool>,
    pub launch_at_login: Option<bool>,
    pub onboarded: Option<bool>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Bootstrap {
    pub settings: Settings,
    pub habits: Vec<Habit>,
    pub today: String,
    pub streak: i64,
    pub legacy_available: bool,
    pub data_dir: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HabitMark {
    pub habit_id: i64,
    pub day: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HabitStat {
    pub habit_id: i64,
    pub name: String,
    pub completions: i64,
    pub rate: f64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Stats {
    pub days: i64,
    pub perfect_days: i64,
    pub active_days: i64,
    pub rate: f64,
    pub best_streak: i64,
    pub per_habit: Vec<HabitStat>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Completion {
    pub habit_id: i64,
    pub day: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DayTarget {
    pub day: String,
    pub total: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Note {
    pub day: String,
    pub body: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportBundle {
    pub version: u32,
    pub exported_at: String,
    pub app: String,
    pub settings: serde_json::Map<String, serde_json::Value>,
    pub habits: Vec<Habit>,
    pub completions: Vec<Completion>,
    pub targets: Vec<DayTarget>,
    pub notes: Vec<Note>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportResult {
    pub habits: usize,
    pub completions: usize,
    pub days: usize,
    pub notes: usize,
}
