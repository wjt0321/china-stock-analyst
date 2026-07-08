#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

use tauri::{Manager, WindowEvent};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            sidecar::spawn_sidecar(&app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                sidecar::reap_sidecar(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![sidecar::send_command])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
