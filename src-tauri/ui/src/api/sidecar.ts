import { invoke } from "@tauri-apps/api/core";

export async function sendCommand<T = unknown>(cmd: object): Promise<T> {
  const response = await invoke<string>("send_command", {
    command: JSON.stringify(cmd),
  });
  return JSON.parse(response) as T;
}

export async function analyzeStock(codes: string[], mode: string = "single") {
  return sendCommand({
    cmd: "analyze",
    codes,
    mode,
    request_id: crypto.randomUUID(),
  });
}

export async function getWatchlist() {
  return sendCommand({ cmd: "watchlist", request_id: crypto.randomUUID() });
}

export async function getSettings() {
  return sendCommand({ cmd: "settings", action: "get", request_id: crypto.randomUUID() });
}
