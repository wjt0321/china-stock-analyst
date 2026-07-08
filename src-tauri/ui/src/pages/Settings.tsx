import { useEffect, useState } from "react";
import { getSettings, sendCommand } from "../api/sidecar";

export default function Settings() {
  const [llmKey, setLlmKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    getSettings().then((res: any) => {
      const cfg = res.data?.llm_config || {};
      setHasKey(Boolean(cfg.api_key));
      setLlmKey(cfg.api_key ? "••••••••" : "");
      setEnabled(Boolean(cfg.enabled));
    });
  }, []);

  const toggleEnabled = async () => {
    const next = !enabled;
    setEnabled(next);
    await sendCommand({
      cmd: "settings",
      action: "set",
      key: "llm_config",
      value: { enabled: next, provider: "deepseek" },
      request_id: crypto.randomUUID(),
    });
  };

  return (
    <div>
      <h1>设置</h1>
      <div style={{ marginBottom: 16 }}>
        <label>
          <input type="checkbox" checked={enabled} onChange={toggleEnabled} disabled={!hasKey} />
          启用 LLM 增强解读
        </label>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label>
          DeepSeek API Key:
          <input type="password" value={llmKey} readOnly style={{ marginLeft: 8, width: 300 }} />
        </label>
      </div>
      <p style={{ color: hasKey ? "green" : "#d32f2f" }}>
        {hasKey
          ? "已检测到 LLM_API_KEY，可以启用增强解读。"
          : "未检测到 LLM_API_KEY。请在项目根目录的 .env 或 .env.local 中配置 LLM_API_KEY，然后重启应用。"}
      </p>
      <p style={{ color: "#666", fontSize: 14 }}>
        出于安全考虑，API Key 不会保存在应用数据库中，仅通过环境变量/.env 文件读取。
      </p>
    </div>
  );
}
