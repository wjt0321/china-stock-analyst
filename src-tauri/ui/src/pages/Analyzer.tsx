import { useEffect, useState } from "react";
import { analyzeStock } from "../api/sidecar";
import Markdown from "../components/Markdown";

const LAST_RESULT_KEY = "china-stock-analyst:last-result";

export default function Analyzer() {
  const [codes, setCodes] = useState("600519");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);

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

  const reports = result?.data || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      <div>
        <h1>分析向导</h1>
        <input
          value={codes}
          onChange={(e) => setCodes(e.target.value)}
          disabled={loading}
          style={{ width: 300, marginRight: 8 }}
          placeholder="输入股票代码，如 600519"
        />
        <button onClick={handleAnalyze} disabled={loading}>
          {loading ? "分析中..." : "开始分析"}
        </button>
        <label style={{ marginLeft: 16 }}>
          <input type="checkbox" checked={showJson} onChange={(e) => setShowJson(e.target.checked)} />
          显示原始 JSON
        </label>
        {loading && <p>正在获取数据，可能需要 30-60 秒...</p>}
        {error && <p style={{ color: "red" }}>错误：{error}</p>}
      </div>

      {reports.length > 0 && (
        <div style={{ flex: 1, overflow: "auto", border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
          {reports.map((item: any) => (
            <div key={item.stock_code} style={{ marginBottom: 32 }}>
              <Markdown content={item.report_md} />
            </div>
          ))}
        </div>
      )}

      {showJson && result && (
        <pre style={{ whiteSpace: "pre-wrap", background: "#f5f5f5", padding: 16, borderRadius: 8 }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
