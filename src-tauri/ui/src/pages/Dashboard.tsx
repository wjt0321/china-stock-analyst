import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getWatchlist, getReports, analyzeStock } from "../api/sidecar";

function parseReportTitle(md: string): string {
  const match = md.match(/^title:\s*(.+)$/m);
  if (match) return match[1].trim();
  const heading = md.match(/^#\s+(.+)$/m);
  if (heading) return heading[1].trim();
  return "分析报告";
}

export default function Dashboard() {
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    getWatchlist().then((res: any) => setWatchlist(res.data || []));
    getReports().then((res: any) => setReports((res.data || []).slice(0, 10)));
  }, []);

  const refreshReports = async () => {
    const res: any = await getReports();
    setReports((res.data || []).slice(0, 10));
  };

  const handleAnalyze = async (code: string) => {
    setLoading(code);
    try {
      await analyzeStock([code]);
      await refreshReports();
    } catch (e: any) {
      alert(`分析失败: ${e?.message || e}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div>
      <h1>自选股看板</h1>
      {watchlist.length === 0 ? (
        <p>暂无自选股。在分析页面点击「加入自选」可添加。</p>
      ) : (
        <ul>
          {watchlist.map((item) => (
            <li key={item.stock_code}>
              {item.stock_code} {item.stock_name}
              <button onClick={() => handleAnalyze(item.stock_code)} disabled={loading === item.stock_code}>
                {loading === item.stock_code ? "分析中..." : "分析"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <h2>最近报告</h2>
      {reports.length === 0 ? (
        <p>暂无报告。在分析页面生成报告后会出现在这里。</p>
      ) : (
        <ul>
          {reports.map((r) => (
            <li key={r.id || `${r.stock_code}-${r.created_at}`}>
              <Link to="/reports" state={{ report: r }}>
                {parseReportTitle(r.report_md)}
              </Link>
              <span style={{ color: "#888", marginLeft: 8, fontSize: 12 }}>
                {r.created_at?.replace("T", " ")?.slice(0, 19)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
