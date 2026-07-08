import { useEffect, useState } from "react";
import { getSettings, sendCommand } from "../api/sidecar";

export default function Settings() {
  const [llmKey, setLlmKey] = useState("");

  useEffect(() => {
    getSettings().then((res: any) => {
      setLlmKey(res.data?.llm_config?.api_key || "");
    });
  }, []);

  const save = async () => {
    await sendCommand({
      cmd: "settings",
      action: "set",
      key: "llm_config",
      value: { enabled: Boolean(llmKey), api_key: llmKey, provider: "deepseek" },
      request_id: crypto.randomUUID(),
    });
    alert("已保存");
  };

  return (
    <div>
      <h1>设置</h1>
      <label>
        DeepSeek API Key:
        <input type="password" value={llmKey} onChange={(e) => setLlmKey(e.target.value)} />
      </label>
      <button onClick={save}>保存</button>
    </div>
  );
}
