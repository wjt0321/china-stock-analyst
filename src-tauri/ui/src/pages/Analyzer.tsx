import { useEffect, useState } from "react";
import { analyzeStock } from "../api/sidecar";

const LAST_RESULT_KEY = "china-stock-analyst:last-result";

export default function Analyzer() {
  const [codes, setCodes] = useState("600519");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LAST_RESULT_KEY);
      if (saved) setResult(JSON.parse(saved));
    } catch {
      // ignore parse errors
    }
  }, []);

  const handleAnalyze = async () => {
    const list = codes.split(/[,，\s]+/).filter(Boolean);
    if (list.length === 0) return;
    setLoading(true);
    setError(null);
    console.log("[Analyzer] starting analyze", list);
    try {
      const res = await analyzeStock(list, list.length > 1 ? "compare" : "single");
      console.log("[Analyzer] analyze result", res);
      setResult(res);
      try {
        localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(res));
      } catch {
        // ignore storage errors
      }
    } catch (e: any) {
      console.error("[Analyzer] analyze failed", e);
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>分析向导</h1>
      <input value={codes} onChange={(e) => setCodes(e.target.value)} disabled={loading} />
      <button onClick={handleAnalyze} disabled={loading}>
        {loading ? "分析中..." : "开始分析"}
      </button>
      {loading && <p>正在获取数据，可能需要 30-60 秒...</p>}
      {error && <p style={{ color: "red" }}>错误：{error}</p>}
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
