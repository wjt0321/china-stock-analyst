import { useState } from "react";
import { analyzeStock } from "../api/sidecar";

export default function Analyzer() {
  const [codes, setCodes] = useState("600519");
  const [result, setResult] = useState<any>(null);

  const handleAnalyze = async () => {
    const list = codes.split(/[,，\s]+/).filter(Boolean);
    const res = await analyzeStock(list, list.length > 1 ? "compare" : "single");
    setResult(res);
  };

  return (
    <div>
      <h1>分析向导</h1>
      <input value={codes} onChange={(e) => setCodes(e.target.value)} />
      <button onClick={handleAnalyze}>开始分析</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
