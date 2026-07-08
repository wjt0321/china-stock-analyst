/// Sidecar management for the desktop application.
///
/// This module is intentionally minimal for the initial Tauri shell. It wires
/// the invoke handler expected by `main.rs` and reserves a hook for spawning
/// the Python backend sidecar once the bundle configuration is added in a
/// later task.

/// Placeholder sidecar spawn hook invoked during Tauri setup.
pub fn spawn_sidecar(_app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    // TODO: spawn the Python sidecar (desktop/service.py) when the external
    // binary is registered in tauri.conf.json.
    Ok(())
}

/// Echo command exposed to the frontend for health checks.
#[tauri::command]
pub fn send_command(command: String) -> String {
    format!("Echo: {}", command)
}
