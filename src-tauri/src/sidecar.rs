use std::collections::VecDeque;
use std::io::{BufRead, Write};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::path::BaseDirectory;
use tauri::{AppHandle, Manager, State};

/// Time to wait for a matching sidecar response before failing the request.
const SIDECAR_RESPONSE_TIMEOUT_SECS: u64 = 180;

pub struct SidecarState {
    pub stdin: Mutex<std::process::ChildStdin>,
    pub output: Mutex<VecDeque<String>>,
    pub child: Mutex<Option<Child>>,
    pub request_counter: Mutex<u64>,
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<(), String> {
    // The committed `python-x86_64-pc-windows-msvc.exe` is a placeholder and
    // `.bat` files cannot be executed through Tauri's sidecar API. Spawn the
    // batch launcher directly with `cmd /c` for the dev workflow.
    let bat_path = app
        .path()
        .resolve("sidecars/python.bat", BaseDirectory::Resource)
        .map_err(|e| format!("Failed to resolve sidecar batch path: {}", e))?;

    let mut cmd = Command::new("cmd");
    cmd.args(["/c", bat_path.to_string_lossy().as_ref()])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // Tell the Python service where to store application data and logs.
    // The service falls back to platform defaults when this is not set.
    if let Ok(app_data_dir) = app.path().app_data_dir() {
        cmd.env("APP_DATA_DIR", app_data_dir);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

    let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to open sidecar stderr")?;

    app.manage(SidecarState {
        stdin: Mutex::new(stdin),
        output: Mutex::new(VecDeque::new()),
        child: Mutex::new(Some(child)),
        request_counter: Mutex::new(0),
    });

    // Dedicated stdout reader: push complete lines into the shared queue.
    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(line) = line {
                if let Some(state) = app_clone.try_state::<SidecarState>() {
                    if let Ok(mut output) = state.output.lock() {
                        output.push_back(line);
                    }
                }
            }
        }
    });

    // Stderr drainer: prevents the sidecar pipe from deadlocking.
    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(line) = line {
                eprintln!("[sidecar stderr] {}", line);
            }
        }
    });

    Ok(())
}

/// Reap the sidecar child process. Called from the window close handler.
pub fn reap_sidecar(app: &AppHandle) {
    if let Some(state) = app.try_state::<SidecarState>() {
        if let Ok(mut child) = state.child.lock() {
            if let Some(mut c) = child.take() {
                let _ = c.kill();
                let _ = c.wait();
            }
        }
    }
}

#[tauri::command]
pub fn send_command(state: State<'_, SidecarState>, command: String) -> Result<String, String> {
    // Parse the incoming command so we can inject a request id if absent.
    let mut command_value: serde_json::Value =
        serde_json::from_str(&command).map_err(|e| e.to_string())?;

    let expected_id = if let Some(id) = command_value.get("request_id").and_then(|v| v.as_str()) {
        id.to_string()
    } else {
        let mut counter = state.request_counter.lock().map_err(|e| e.to_string())?;
        *counter += 1;
        let id = format!("req-{}", *counter);
        command_value["request_id"] = serde_json::Value::String(id.clone());
        id
    };

    let command = command_value.to_string();

    {
        let mut stdin = state.stdin.lock().map_err(|e| e.to_string())?;
        writeln!(stdin, "{}", command).map_err(|e| e.to_string())?;
        stdin.flush().map_err(|e| e.to_string())?;
    }

    // Wait for a response line whose request_id matches the sent command.
    let deadline =
        std::time::Instant::now() + std::time::Duration::from_secs(SIDECAR_RESPONSE_TIMEOUT_SECS);
    loop {
        if std::time::Instant::now() > deadline {
            return Err("Sidecar response timeout".to_string());
        }

        let mut output = state.output.lock().map_err(|e| e.to_string())?;
        let mut i = 0;
        while i < output.len() {
            let line = output[i].clone();
            match serde_json::from_str::<serde_json::Value>(&line) {
                Ok(value) => {
                    if value
                        .get("request_id")
                        .and_then(|v| v.as_str())
                        == Some(&expected_id)
                    {
                        output.remove(i);
                        return Ok(line);
                    }
                }
                Err(_) => {
                    // Drop malformed lines; they cannot be matched to a request.
                    output.remove(i);
                    continue;
                }
            }
            i += 1;
        }

        // Release the lock while sleeping so the reader thread can append lines.
        drop(output);
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}
