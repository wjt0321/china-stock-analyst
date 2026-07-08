import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getReports, deleteReport } from "../api/sidecar";
import Markdown from "../components/Markdown";

interface ReportItem {
  id: number;
  stock_code: string;
  created_at: string;
  report_md: string;
}

function parseReportTitle(md: string): string {
  // Try to extract the YAML frontmatter title line.
  const match = md.match(/^title:\s*(.+)$/m);
  if (match) {
    return match[1].trim();
  }
  // Fallback to first heading.
  const heading = md.match(/^#\s+(.+)$/m);
  if (heading) {
    return heading[1].trim();
  }
  return "分析报告";
}

export default function ReportViewer() {
  const location = useLocation();
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [selected, setSelected] = useState<ReportItem | null>(null);

  const loadReports = async () => {
    const res: any = await getReports();
    const list = (res.data || []) as ReportItem[];
    list.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    setReports(list);
    const preselected = (location.state as any)?.report;
    if (preselected && list.some((r) => r.id === preselected.id)) {
      setSelected(list.find((r) => r.id === preselected.id) || null);
    } else if (list.length > 0 && !selected) {
      setSelected(list[0]);
    } else if (list.length === 0) {
      setSelected(null);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  const handleDelete = async (e: React.MouseEvent, report: ReportItem) => {
    e.stopPropagation();
    if (!window.confirm(`确定删除 ${parseReportTitle(report.report_md)} 吗？`)) {
      return;
    }
    try {
      await deleteReport(report.id);
      await loadReports();
    } catch (err: any) {
      alert("删除失败：" + (err?.message || String(err)));
    }
  };

  return (
    <div style={{ display: "flex", gap: 16, height: "100%", overflow: "hidden" }}>
      <div style={{ minWidth: 280, overflow: "auto" }}>
        <h2>报告列表</h2>
        {reports.length === 0 ? (
          <p>暂无报告</p>
        ) : (
          <ul style={{ paddingLeft: 16 }}>
            {reports.map((r) => (
              <li
                key={r.id}
                style={{
                  cursor: "pointer",
                  fontWeight: selected?.id === r.id ? "bold" : "normal",
                  marginBottom: 12,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
                onClick={() => setSelected(r)}
              >
                <span style={{ flex: 1, wordBreak: "break-all" }}>
                  {parseReportTitle(r.report_md)}
                </span>
                <button
                  onClick={(e) => handleDelete(e, r)}
                  style={{
                    marginLeft: 8,
                    color: "#d32f2f",
                    border: "1px solid #d32f2f",
                    background: "#fff",
                    borderRadius: 4,
                    cursor: "pointer",
                  }}
                >
                  删除
                </button>
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
