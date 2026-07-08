export default function ReportViewer({ report }: { report: any }) {
  if (!report) return null;
  return (
    <div className="report">
      <pre>{report.report_md}</pre>
    </div>
  );
}
