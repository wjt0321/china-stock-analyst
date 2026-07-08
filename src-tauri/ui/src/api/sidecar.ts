import { invoke } from "@tauri-apps/api/core";

export async function sendCommand<T = unknown>(cmd: object): Promise<T> {
  const payload = JSON.stringify(cmd);
  console.log("[sidecar] invoke send_command", payload);
  const response = await invoke<string>("send_command", {
    command: payload,
  });
  console.log("[sidecar] raw response", response);
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
  return sendCommand({ cmd: "watchlist", action: "get", request_id: crypto.randomUUID() });
}

export async function addWatchlist(stockCode: string, stockName: string = "") {
  return sendCommand({
    cmd: "watchlist",
    action: "add",
    stock_code: stockCode,
    stock_name: stockName,
    request_id: crypto.randomUUID(),
  });
}

export async function removeWatchlist(stockCode: string) {
  return sendCommand({
    cmd: "watchlist",
    action: "remove",
    stock_code: stockCode,
    request_id: crypto.randomUUID(),
  });
}

export async function getSettings() {
  return sendCommand({ cmd: "settings", action: "get", request_id: crypto.randomUUID() });
}

export async function getReports(stockCode?: string) {
  return sendCommand({
    cmd: "reports",
    action: "get",
    stock_code: stockCode,
    request_id: crypto.randomUUID(),
  });
}

export async function deleteReport(reportId: number) {
  return sendCommand({
    cmd: "reports",
    action: "delete",
    report_id: reportId,
    request_id: crypto.randomUUID(),
  });
}
