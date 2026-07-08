import { useState } from "react";
import { getWatchlist } from "../api/sidecar";

export default function ReportViewer() {
  const [reports, setReports] = useState<any[]>([]);

  const handleLoad = async () => {
    const res: any = await getWatchlist();
    setReports(res.data || []);
  };

  return (
    <div>
      <h1>报告浏览</h1>
      <button onClick={handleLoad}>加载列表</button>
      <ul>
        {reports.map((item) => (
          <li key={item.stock_code}>
            {item.stock_code} {item.stock_name}
          </li>
        ))}
      </ul>
    </div>
  );
}
