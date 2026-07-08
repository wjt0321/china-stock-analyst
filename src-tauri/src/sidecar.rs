use std::collections::VecDeque;
use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

/// Time to wait for a matching sidecar response before failing the request.
const SIDECAR_RESPONSE_TIMEOUT_SECS: u64 = 180;

/// Locate a working Python executable.
/// Prefer a system install (PY_PYTHON, PYTHON_EXE env vars, or common paths),
/// then fall back to searching PATH for `python`/`python3`.
fn find_python_exe() -> PathBuf {
    if let Ok(exe) = std::env::var("PYTHON_EXE") {
        let p = PathBuf::from(exe);
        if p.exists() {
            return p;
        }
    }

    let candidates: Vec<PathBuf> = [
        r"C:\Python314\python.exe",
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Program Files\Python314\python.exe",
        r"C:\Program Files\Python313\python.exe",
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
        r"C:\Program Files\Python310\python.exe",
    ]
    .iter()
    .map(PathBuf::from)
    .collect();

    for c in &candidates {
        if c.exists() {
            return c.clone();
        }
    }

    // Last resort: search PATH for python / python3.
    if let Ok(path_env) = std::env::var("PATH") {
        for name in ["python.exe", "python3.exe"] {
            for dir in std::env::split_paths(&path_env) {
                let candidate = dir.join(name);
                if candidate.exists() {
                    return candidate;
                }
            }
        }
    }

    PathBuf::from("python")
}

pub struct SidecarState {
    pub stdin: Mutex<std::process::ChildStdin>,
    pub output: Mutex<VecDeque<String>>,
    pub child: Mutex<Option<Child>>,
    pub request_counter: Mutex<u64>,
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<(), String> {
    // The committed `python-x86_64-pc-windows-msvc.exe` is a placeholder and
    // `.bat` files cannot be executed through Tauri's sidecar API. Spawn the
    // system Python directly for the dev workflow.
    //
    // In dev mode the executable lives at:
    //   <project_root>/src-tauri/target/debug/china-stock-analyst-desktop.exe
    // so we derive the project root by walking up from the executable path.
    let exe_path = std::env::current_exe().map_err(|e| format!("Failed to get current exe: {}", e))?;
    let exe_dir = exe_path.parent().ok_or("Executable has no parent directory")?;
    // src-tauri/target/debug -> src-tauri/target -> src-tauri -> project_root
    let project_root: PathBuf = [exe_dir, Path::new(".."), Path::new(".."), Path::new("..")]
        .iter()
        .collect::<PathBuf>()
        .canonicalize()
        .map_err(|e| format!("Failed to canonicalize project root: {}", e))?;
    let service_path = project_root.join("desktop").join("service.py");

    if !service_path.exists() {
        return Err(format!(
            "service.py not found at {}; project root derived as {}",
            service_path.display(),
            project_root.display()
        ));
    }

    eprintln!("[sidecar] spawning python {} (project root: {})", service_path.display(), project_root.display());

    // Use an absolute Python path to avoid resolving a potentially incompatible
    // `python` shim from the parent process's PATH (e.g., Node/npm installed ones).
    let python_exe = find_python_exe();
    eprintln!("[sidecar] using python executable: {}", python_exe.display());

    let mut cmd = Command::new(&python_exe);
    cmd.arg(&service_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .current_dir(&project_root);

    // Make sure desktop.* and scripts.* packages are importable.
    let pythonpath = std::env::var("PYTHONPATH").unwrap_or_default();
    cmd.env("PYTHONPATH", format!("{};{}", project_root.display(), pythonpath));

    // Tell the Python service where to store application data and logs.
    // The service falls back to platform defaults when this is not set.
    if let Ok(app_data_dir) = app.path().app_data_dir() {
        cmd.env("APP_DATA_DIR", app_data_dir);
    }

    // Force UTF-8 for stdout/stderr so the Rust reader can decode responses
    // reliably on Windows systems where the default console code page is GBK.
    cmd.env("PYTHONIOENCODING", "utf-8");
    cmd.env("PYTHONUTF8", "1");

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
        eprintln!("[sidecar] stdout reader thread ended; sidecar process likely exited");
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
    eprintln!("[sidecar] received command: {}", command);
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
