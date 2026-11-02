mod commands;
mod db;
mod error;
mod models;
mod tray;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .setup(|app| {
            let db = db::Db::open()?;
            let _ = db.auto_backup();
            let dir = db.dir().to_path_buf();
            app.manage(commands::AppState { db, dir });
            tray::setup(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let minimize = window
                    .app_handle()
                    .try_state::<commands::AppState>()
                    .and_then(|state| state.db.minimize_to_tray().ok())
                    .unwrap_or(true);
                if minimize {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::bootstrap,
            commands::get_day,
            commands::toggle_completion,
            commands::range_summary,
            commands::completions_range,
            commands::list_habits,
            commands::list_archived_habits,
            commands::create_habit,
            commands::rename_habit,
            commands::reorder_habits,
            commands::archive_habit,
            commands::restore_habit,
            commands::delete_habit,
            commands::get_settings,
            commands::update_settings,
            commands::streak,
            commands::stats,
            commands::get_note,
            commands::set_note,
            commands::export_to,
            commands::import_from,
            commands::backup_now,
            commands::import_legacy
        ])
        .run(tauri::generate_context!())
        .expect("error while running span");
}
