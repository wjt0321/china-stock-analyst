import { useEffect, useState } from "react";
import { getReports } from "../api/sidecar";
import Markdown from "../components/Markdown";

export default function ReportViewer() {
  const [reports, setReports] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    getReports().then((res: any) => {
      const list = res.data || [];
      // Show newest first.
      list.sort((a: any, b: any) => (b.created_at || "").localeCompare(a.created_at || ""));
      setReports(list);
      if (list.length > 0 && !selected) setSelected(list[0]);
    });
  }, []);

  return (
    <div style={{ display: "flex", gap: 16, height: "100%", overflow: "hidden" }}>
      <div style={{ minWidth: 220, overflow: "auto" }}>
        <h2>报告列表</h2>
        {reports.length === 0 ? (
          <p>暂无报告</p>
        ) : (
          <ul style={{ paddingLeft: 16 }}>
            {reports.map((r) => (
              <li
                key={r.id || `${r.stock_code}-${r.created_at}`}
                style={{
                  cursor: "pointer",
                  fontWeight: selected?.id === r.id ? "bold" : "normal",
                  marginBottom: 8,
                }}
                onClick={() => setSelected(r)}
              >
                {r.stock_code} - {r.created_at?.slice(0, 10)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div style={{ flex: 1, overflow: "auto", border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        {selected ? (
          <Markdown content={selected.report_md} />
        ) : (
          <p>请从左侧选择一份报告</p>
        )}
      </div>
    </div>
  );
}
