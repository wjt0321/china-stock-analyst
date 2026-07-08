#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            sidecar::spawn_sidecar(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar::send_command])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
