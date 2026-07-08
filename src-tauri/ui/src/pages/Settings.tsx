import { useState } from "react";

export default function Settings() {
  const [theme, setTheme] = useState("light");

  return (
    <div>
      <h1>设置</h1>
      <label>
        主题：
        <select value={theme} onChange={(e) => setTheme(e.target.value)}>
          <option value="light">浅色</option>
          <option value="dark">深色</option>
        </select>
      </label>
    </div>
  );
}
