import { useEffect, useState } from "react";
import { getReports } from "../api/sidecar";

export default function ReportViewer() {
  const [reports, setReports] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    getReports().then((res: any) => {
      const list = res.data || [];
      setReports(list);
      if (list.length > 0 && !selected) setSelected(list[0]);
    });
  }, []);

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div style={{ minWidth: 200 }}>
        <h2>报告列表</h2>
        {reports.length === 0 ? (
          <p>暂无报告</p>
        ) : (
          <ul>
            {reports.map((r) => (
              <li
                key={r.id || `${r.stock_code}-${r.created_at}`}
                style={{ cursor: "pointer", fontWeight: selected?.id === r.id ? "bold" : "normal" }}
                onClick={() => setSelected(r)}
              >
                {r.stock_code} - {r.created_at}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div style={{ flex: 1 }}>
        {selected ? (
          <>
            <h1>{selected.stock_code} 分析报告</h1>
            <pre style={{ whiteSpace: "pre-wrap" }}>{selected.report_md}</pre>
          </>
        ) : (
          <p>请从左侧选择一份报告</p>
        )}
      </div>
    </div>
  );
}
