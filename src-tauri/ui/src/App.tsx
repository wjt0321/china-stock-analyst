import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Analyzer from "./pages/Analyzer";
import ReportViewer from "./pages/ReportViewer";
import Settings from "./pages/Settings";

function ReportViewerPage() {
  const location = useLocation();
  return <ReportViewer report={(location.state as any)?.report} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">看板</Link> | <Link to="/analyze">分析</Link> | <Link to="/reports">报告</Link> | <Link to="/settings">设置</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyze" element={<Analyzer />} />
        <Route path="/reports" element={<ReportViewerPage />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  );
}
