use std::io::Write;
use std::process::Stdio;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::ShellExt;

pub struct SidecarState {
    pub stdin: Mutex<std::process::ChildStdin>,
    pub output: Mutex<String>,
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<(), String> {
    let sidecar_command = app
        .shell()
        .sidecar("sidecars/python")
        .map_err(|e| e.to_string())?;

    let mut child: std::process::Child = std::process::Command::from(
        sidecar_command.arg("desktop/service.py"),
    )
    .stdin(Stdio::piped())
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
    .spawn()
    .map_err(|e| e.to_string())?;

    let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;

    app.manage(SidecarState {
        stdin: Mutex::new(stdin),
        output: Mutex::new(String::new()),
    });

    // Spawn stdout reader
    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        use std::io::BufRead;
        for line in reader.lines() {
            if let Ok(line) = line {
                if let Some(state) = app_clone.try_state::<SidecarState>() {
                    if let Ok(mut output) = state.output.lock() {
                        output.push_str(&line);
                        output.push('\n');
                    }
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub fn send_command(state: State<'_, SidecarState>, command: String) -> Result<String, String> {
    let mut stdin = state.stdin.lock().map_err(|e| e.to_string())?;
    writeln!(stdin, "{}", command).map_err(|e| e.to_string())?;
    stdin.flush().map_err(|e| e.to_string())?;

    // Simple synchronous read: wait for one line of output
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(60);
    loop {
        if std::time::Instant::now() > deadline {
            return Err("Sidecar response timeout".to_string());
        }
        {
            let output = state.output.lock().map_err(|e| e.to_string())?;
            if !output.is_empty() {
                let mut lines: Vec<&str> = output.lines().collect();
                if let Some(line) = lines.pop() {
                    // Note: real implementation needs proper line queue, this is illustrative
                    return Ok(line.to_string());
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}
